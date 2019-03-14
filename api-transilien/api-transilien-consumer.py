import os
import json
import time
import logging
import numpy as np
from scipy.interpolate import interp1d
from pyspark.sql import SparkSession
import pyspark.sql.types as st
import pyspark.sql.functions as sf
from pyspark.sql.window import Window as spark_window
from py4j.java_gateway import java_import


log4j = sc._jvm.org.apache.log4j
log4j.LogManager.getRootLogger().setLevel(log4j.Level.ERROR)

# --------------------------------------------------------------------
# load trains paths data (geolocalized paths from station to station)
with open("./scnf-paths-line-l.json", "r", encoding="utf-8") as f:
    g_trains_paths = json.load(f)

# --------------------------------------------------------------------
def accurate_latitude(from_station, to_station, progression):  
    # compute accurate latitude
    # will be attached to TransilienStreamProcessor.alt_udf
    return accurate_train_position('lat', from_station, to_station, progression)

# --------------------------------------------------------------------
def accurate_longitude(from_station, to_station, progression):  
    # compute accurate longitude
    # will be attached to TransilienStreamProcessor.alg_udf
    return accurate_train_position('lon', from_station, to_station, progression)  

# --------------------------------------------------------------------
def accurate_train_position(geo_component, from_station, to_station, train_progression):
    # compute accurate 'lat'itude or 'lon'gitude of a given train
    # the interpolation is done along the paths stored into <g_trains_paths>
    path_from_st_to_st = g_trains_paths[f"{from_station}-{to_station}"]
    # special case for 'standby trains' (trains waiting for departure)
    if from_station == to_station:
        if geo_component == 'lat':
            geo_pos = float(path_from_st_to_st["geoPoints"][0]["latitude"])
        else:
            geo_pos = float(path_from_st_to_st["geoPoints"][0]["longitude"])
    else:    
        # the scipy cubic spline interpolator doesn't like short interpolation domains 
        # use cubic spline when the number of points between from_station & to_station is above 4
        interpolator = 'linear' if path_from_st_to_st["number_step"] <= 4 else 'cubic'
        # prepare data for interpolator: progression axis in % 
        x = np.linspace(0., 100., num=path_from_st_to_st["number_step"], endpoint=True)
        # interpolation of the requested pos. component (latitude or longitude)
        if geo_component == 'lat':
             # prepare data for interpolator: latitude axis
            lat_y = [float(point["latitude"]) for point in path_from_st_to_st["geoPoints"]]
            # get latitude for the cuurent 'train_progression'
            geo_pos = float(interp1d(x, lat_y, kind=interpolator)(train_progression))
        else:
            # prepare data for interpolator: longitude axis 
            lon_y = [float(point["longitude"]) for point in path_from_st_to_st["geoPoints"]]
            # get longitude for the cuurent 'train_progression'
            geo_pos = float(interp1d(x, lon_y, kind=interpolator)(train_progression))
    # return current latitude and longitude values
    return geo_pos
    
 
 # -------------------------------------------------------------------------------
class TransilienStreamProcessor():
    
    # unique TransilienStreamProcessor instance
    singleton = None
    
    # spark user defined fonction: accurate latitude computation
    alt_udf = sf.udf(accurate_latitude, st.FloatType())
    
    # spark user defined fonction: accurate longitude computation
    alg_udf = sf.udf(accurate_longitude, st.FloatType())
    
    # -------------------------------------------------------------------------------
    def __init__(self, config):
    # -------------------------------------------------------------------------------  
        # store the configuration 
        self.config = config
        
        # setup logging: timestamp of the last cell clearing (no log  accumulation in nb. cell)
        self.last_clear_outputs_ts = time.time()
        # setup logging: show/display train progression table (computation result)
        self.show_trprg_table = self.config.get('show_trprg_table', False)
        
        
        # release any existing instance
        if TransilienStreamProcessor.singleton is not None:
            self.warning("TSP:releasing existing instance...")
            try:
                TransilienStreamProcessor.singleton.stop()
                del(TransilienStreamProcessor.singleton)
            except Exception as e:
                print(e)
            self.warning("TSP:`-> done!")
            
        # self is the unique TransilienStreamProcessor instance
        TransilienStreamProcessor.singleton = self
  
        # enable 'accurate trains position' computation
        self.accurate_trains_position_enabled = True
        
        self.debug("TSP:initializing...")
        
        # kafka oriented spark session (i.e. configured to process incoming Kafka messages)
        # we notably specify the thrift server mode and port
        self.debug(f"TSP:creating kafka oriented spark session")
        self.kafka_session = SparkSession \
            .builder \
            .master("yarn") \
            .appName("MS-SIO-HADOOP-PROJECT-STREAM") \
            .config("spark.sql.shuffle.partitions", self.config['spark_sql_shuffle_partitions']) \
            .config('spark.sql.hive.thriftServer.singleSession', True) \
            .config('hive.server2.thrift.port', self.config['hive_thrift_server_port']) \
            .enableHiveSupport() \
            .getOrCreate()
        self.debug("`-> done!")
                
        # average waiting time on the last hour of data (awt): kafka stream setup
        self.debug(f"TSP:initializing 'last hour awt' stream")
        self.last_hour_awt_stream = self.__setup_last_hour_awt_stream()
        self.debug("`-> done!")
        
        # real time trains progression: kafka stream setup
        self.debug(f"TSP:initializing 'trains progression' stream")
        self.trains_progression_stream = self.__setup_trains_progression_stream()
        self.debug("`-> done!")
        
        # start our own thrift server
        # this will allow to expose the temp. views and make them reachable from Tableau Software   
        self.__start_thrift_server()
            
        # create a temp. view for the transilien stations data (label, geo.loc., ...)
        # this will allow to expose this data and make them reachable from Tableau Software
        self.stations_data = self.__create_stations_view()
        
        # average waiting time on the last hour of data (awt): computation streaming query
        # acts as a trigger for computeAwtMetricsAndSaveAsTempViews (forEachBatch callback)
        self.lhawt_sink = None
        
        # average waiting time on the last hour of data (awt): console logging streaming query
        # this will allow to print batches into the console  
        self.lhawt_console_sink = None
        
        # real time trains progression (trprg): computation streaming query
        # acts as a trigger for computeTrainsProgressionAndSaveAsTempView (forEachBatch callback)
        self.trprg_sink = None

        # optional TrainsTracker (see TrainsTracker class below - dynamic geoloc. plot)
        self.trains_tracker = None
    
        # start the streaming queries?
        if self.config['auto_start']:
            self.start()
        
        self.debug(f"initialization done!")
        
        # set actual logging level (the one specified by the configuration)
        self.set_logging_level(logging.DEBUG if self.config['verbose'] else logging.ERROR)
        
    # -------------------------------------------------------------------------------
    def __start_thrift_server(self):
    # -------------------------------------------------------------------------------
        # start our own thrift server
        # port and mode were specified at 'kafka_session' instanciation
        # ---------------------------------------------------------------------------
        # note: there is now way to stop the server once started! there's also no way
        # note: to check whether or not the thrift server is already running! we 
        # note: consequently have to restart our python kernel  each time we want to 
        # note: change something into the code - that's real annoying! the best 
        # note: workaround we have is to start the server is it's not already running!
        # ---------------------------------------------------------------------------
        def __is_thrift_server_running(port):
            import socket
            thrift_server_running = False
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("localhost", port))
                s.close()
                thrift_server_running = True
            except ConnectionRefusedError:
                pass
            return thrift_server_running
        htsp = self.config['hive_thrift_server_port']
        if __is_thrift_server_running(htsp):
            wm = f"TSP:thrift server running on port {htsp}"
            self.warning(wm) 
            return
        try:
            self.debug(f"TSP:starting thrift server on port {htsp}") 
            #sc.setLogLevel('INFO')
            java_import(sc._gateway.jvm,"")
            sc._gateway.jvm.org.apache.spark.sql \
                       .hive.thriftserver.HiveThriftServer2 \
                       .startWithContext(spark._jwrapped)
            #sc.setLogLevel('ERROR')       
            self.debug(f"TSP:thrift server successfully started") 
        except Exception as e:
            self.error(e)
                       
    # -------------------------------------------------------------------------------
    def __create_stations_view(self):
    # -------------------------------------------------------------------------------
        # read then save stations data as a tmep view so that we can retrieve it from
        # Tableau Software (or any client having the ability to talk to our thrift server)         
        df = self.kafka_session \
            .read \
            .format("csv") \
            .option("sep", ",") \
            .option("inferSchema", "true") \
            .option("header", "true") \
            .load("file:/root/ms-sio-hdp/api-transilien/transilien_line_l_stations_by_code.csv")
        df.createOrReplaceTempView("stations_data")
        return df
                       
    # -------------------------------------------------------------------------------
    def enable_accurate_trains_position(self):
    # -------------------------------------------------------------------------------
         # enable 'accurate trains position' feature
         self.accurate_trains_position_enabled = True
    
    # -------------------------------------------------------------------------------
    def disable_accurate_trains_position(self):
    # -------------------------------------------------------------------------------
         # disable 'accurate trains position' feature
         self.accurate_trains_position_enabled = False
                
    # -------------------------------------------------------------------------------
    def __setup_last_hour_awt_stream(self):
    # -------------------------------------------------------------------------------
        # setup stream for the 'average waiting time on the last hour of data' 
        # --------------------------------------------------------------------
        # processing sequence comments:
        # 1 - create the kafka stream
        # 2 - extract data from kafka messages (i.e. deserialization) 
        # 3 - set watermark (using kafka_lhawt_stream_watermark config parameter)
        # 4 - drop (train, departure-time) duplicates         
        # 5 - setup sliding window (using config parameters)
        # 6 - count trains in each window & compute average waiting time 
        # 7 - select 'last hour window'
        # 8 - drop temp. columns
        # --------------------------------------------------------------------
        # setup the streaming window
        wm = float(self.config['kafka_lhawt_stream_watermark'])
        wl = float(self.config['kafka_lhawt_stream_window_length'])
        si = float(self.config['kafka_lhawt_stream_sliding_interval'])
        streaming_window = sf.window("timestamp", f"{int(wl)} minutes", f"{int(si)} minutes")
        oha_offset = int((wl + si) * 60.)
        now_offset = int(60. * si / 2.)
        # setup our kafka stream
        return self.kafka_session \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.config['kafka_broker']) \
            .option("subscribe", self.config['kafka_topic']) \
            .option("spark.streaming.kafka.consumer.poll.ms", 100) \
            .option("startingOffsets", "earliest") \
            .load() \
            .select(sf.from_json(sf.col("value").cast("string"), 
                                 self.config['json_schema'], 
                                 self.config['json_options']).alias("departure")) \
            .select("departure.*") \
            .withWatermark("timestamp", f"{int(wm)} minutes") \
            .dropDuplicates(["train", "timestamp"]) \
            .groupBy("station", streaming_window) \
            .agg(sf.count("train").alias("nt"), \
                 sf.format_number(wl / sf.count("train"), 1).cast("double").alias("awt")) \
            .withColumn("oha", sf.unix_timestamp(sf.current_timestamp()) - oha_offset) \
            .withColumn("now", sf.unix_timestamp(sf.current_timestamp()) - now_offset) \
            .withColumn("wstart", sf.unix_timestamp("window.start")) \
            .withColumn("wend", sf.unix_timestamp("window.end")) \
            .where((sf.col("oha") <= sf.col("wstart")) & (sf.col("wend") <= sf.col("now"))) \
            .drop("oha", "now", "wstart", "wend")
      
    # -------------------------------------------------------------------------------
    def __setup_trains_progression_stream(self):
    # -------------------------------------------------------------------------------
        # setup stream for trains progression 
        # --------------------------------------------------------------------
        # processing sequence comments:
        # 1 - create the kafka stream
        # 2 - extract data from kafka messages (i.e. deserialization) 
        # 3 - drop (train, departure-time) duplicates
        # 4 - filter on departure-time mode ('R' only)
        # 5 - convert departure time (i.e. timestamp) to unix timestamp then drop initial column
        # 6 - filter on 'time window' (keep only trains which departure time is in now +/- half-time-window) 
        # 7 - execute a 'dummy' aggregation so that we can work in 'complete' mode (nice trick)
        # 8 - order by ("train", "departure", "station")
        # --------------------------------------------------------------------
        time_window = config['kafka_trprg_time_window']            
        return self.kafka_session \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "sandbox-hdp.hortonworks.com:6667") \
            .option("subscribe", "transilien-02") \
            .option("spark.streaming.kafka.consumer.poll.ms", 100) \
            .option("startingOffsets", "earliest") \
            .load() \
            .select(sf.from_json(sf.col("value").cast("string"), \
                                 self.config['json_schema'], \
                                 self.config['json_options']).alias("departure")) \
            .select("departure.*") \
            .dropDuplicates(["train", "timestamp"]) \
            .filter("mode='R'") \
            .withColumn("departure", sf.unix_timestamp("timestamp")).drop("timestamp") \
            .where(sf.col("departure") \
            .between(sf.unix_timestamp(sf.current_timestamp()) - int(time_window/2.), \
                                       sf.unix_timestamp(sf.current_timestamp()) + int(time_window/2.))) \
            .groupBy("train", "station", "departure", "mode", "mission", "terminus") \
            .agg(sf.count("train").alias("tmp")).drop("tmp") \
            .orderBy("train", "departure", "station")
                       
    # -------------------------------------------------------------------------------
    def start(self):
    # -------------------------------------------------------------------------------
        # start streaming queries
        self.start_last_hour_awt_stream()
        self.start_trains_progress_stream()
     
    # -------------------------------------------------------------------------------
    def stop(self):
    # -------------------------------------------------------------------------------
        # stop streaming queries
        self.stop_last_hour_awt_stream()
        self.stop_trains_progress_stream()
           
    # -------------------------------------------------------------------------------
    def await_termination(self):
    # -------------------------------------------------------------------------------
        if self.lhawt_sink is not None:
            try:
                self.lhawt_sink.awaitTermination()
            except Exception as e:
                self.debug(e)
        if self.lhawt_console_sink is not None:
            try:
                self.lhawt_console_sink.awaitTermination()
            except Exception as e:
                self.debug(e)
        if self.trprg_sink is not None:
            try:
                self.trprg_sink.awaitTermination()
            except Exception as e:
                self.debug(e)
                
    # -------------------------------------------------------------------------------
    def start_last_hour_awt_stream(self):
    # -------------------------------------------------------------------------------
        # stop the streaming queries if already running
        self.stop_last_hour_awt_stream()            
        # processing time of the queries
        proc_time = f"{self.config.get('kafka_lhawt_processing_time', 5.)} seconds"     
        # last hour awt: create then start the (computation) streaming query
        # also make 'self.computeAwtMetricsAndSaveAsTempViews' the 'foreachBatch' callback
        self.debug(f"TSP:starting 'awt' sink (stream query)")
        self.lhawt_sink =  self.last_hour_awt_stream \
                            .writeStream \
                            .trigger(processingTime=proc_time) \
                            .foreachBatch(self.computeAwtMetricsAndSaveAsTempViews) \
                            .outputMode("complete") \
                            .start()
        self.debug(f"`-> done!")    
        if self.config.get('kafka_lhawt_console_sink_enabled', False):
            # last hour awt: create then start the (console) streaming query
            self.debug(f"TSP:starting 'awt' console stream (stream query)")
            self.lhawt_console_sink = self.last_hour_awt_stream \
                                .orderBy("awt") \
                                .writeStream \
                                .trigger(processingTime=proc_time) \
                                .outputMode("complete") \
                                .format("console") \
                                .option("truncate", False) \
                                .start() 
        self.debug(f"`-> done!")
                       
    # -------------------------------------------------------------------------------
    def start_trains_progress_stream(self):
    # -------------------------------------------------------------------------------
        # stop the streaming queries if already running
        self.stop_trains_progress_stream()
        # trains progression: create then start the hive sink (streaming query)
        # also make 'self.computeTrainsProgressionAndSaveAsTempView' the 'foreachBatch' callback
        self.debug(f"TSP:starting trains progression sink (stream query)")
        self.trprg_sink = self.trains_progression_stream \
                            .writeStream \
                            .foreachBatch(self.computeTrainsProgressionAndSaveAsTempView) \
                            .outputMode("complete") \
                            .start()
        self.debug(f"`-> done!")
        self.debug(f"TSP:streaming queries are running")
                       
    # -------------------------------------------------------------------------------
    def stop_last_hour_awt_stream(self):
    # -------------------------------------------------------------------------------
        # stop the streaming queries (best effort impl.)
        if self.lhawt_sink is  not None:
            try:
                self.debug(f"TSP:stopping 'awt' sink (stream query)")
                self.lhawt_sink.stop()
            except Exception as e:
                pass
            finally:
                self.lhawt_sink = None
                self.debug(f"`-> done!")
        if self.lhawt_console_sink is  not None:
            try:
                self.debug(f"TSP:stopping 'awt' console sink (stream query)")
                self.lhawt_console_sink.stop()
            except Exception as e:
                pass
            finally:
                self.lhawt_console_sink = None
                self.debug(f"`-> done!")
   
    # -------------------------------------------------------------------------------
    def stop_trains_progress_stream(self):
    # -------------------------------------------------------------------------------
        # stop the streaming queries (best effort impl.)
        if self.trprg_sink is  not None:
            try:
                self.debug(f"TSP:stopping trains progression sink (stream query)")
                self.trprg_sink.stop()
            except Exception as e:
                pass
            finally:
                self.trprg_sink = None
                self.debug(f"`-> done!")
                       
    # -------------------------------------------------------------------------------
    def cleanup(self):
    # -------------------------------------------------------------------------------
        # cleanup the underlying session 
        # TODO: not sure this is the right way to do the job
        self.stop()
        self.debug(f"TSP:shutting down Kafka-SparkSession")
        self.kafka_session.stop()
        self.debug(f"`-> done!")
      
    # -------------------------------------------------------------------------------
    def turnVerboseOn(self):
    # -------------------------------------------------------------------------------
        # turn verbose on          
        self.set_logging_level(logging.DEBUG)
       
    # -------------------------------------------------------------------------------
    def turnVerboseOff(self):
    # -------------------------------------------------------------------------------
        # turn verbose off   
        self.set_logging_level(logging.ERROR)
                       
    # -------------------------------------------------------------------------------
    def clearOutputs(self):
    # -------------------------------------------------------------------------------
        # clear outputs (i.e. clear our 'mother notebook-cell')
        clear_outputs_period = self.config.get('clear_outputs_period', 15)
        if (time.time() - self.last_clear_outputs_ts) > clear_outputs_period:
            self.clear_output()
            self.last_clear_outputs_ts = time.time()
   
    # -------------------------------------------------------------------------------
    def showTrainsProgressionTable(self):
    # -------------------------------------------------------------------------------
        # trains progression table will be diplayed        
        self.show_trprg_table = True
       
    # -------------------------------------------------------------------------------
    def hideTrainsProgressionTable(self):
    # -------------------------------------------------------------------------------
        # trains progression table will NOT be diplayed 
        self.show_trprg_table = False
                       
    # -------------------------------------------------------------------------------
    def computeAwtMetricsAndSaveAsTempViews(self, batch, batch_number):
    # -------------------------------------------------------------------------------
        # PART-I: COMPUTE AVERAGE WAITING TIME METRICS
        # --------------------------------------------
        # this 'forEachBatch' callback is attached to the our 'lhawt_sink' (streaming query)
        try:
            # clear cell content so that we don't cumulate the log 
            self.clearOutputs()
                              
            # be sure we have some data to handle (incoming dataframe not empty)
            # this will avoid creating empty tables on Hive side 
            if batch.rdd.isEmpty():
                self.warning(f"TSP:computeAwtMetrics: ignoring empty batch #{batch_number}")
                return

            self.debug(f"TSP:entering computeAwtMetrics for batch #{batch_number}...")
                              
            # PART-I: Q1.1 & Q1.3: ordered average waiting time in minutes (over last hour)
            self.debug(f"computing ordered average waiting time...")
            t = time.time()
            tmp = batch.orderBy(sf.asc("awt")).select(batch.station, batch.awt)    
            self.kafka_session.createDataFrame(tmp.rdd).createOrReplaceTempView("ordered_awt")
            self.debug(f"`-> took {round(time.time() - t, 2)} s")
                                                                  
            # PART-I: Q1.2: global average waiting time in minutes (over last hour)
            self.debug(f"computing global average waiting time...")
            t = time.time()
            tmp = batch.agg(sf.count("station").alias("number_of_stations"), 
                            sf.avg("awt").alias("global_awt"))
            self.kafka_session.createDataFrame(tmp.rdd).createOrReplaceTempView("global_awt")
            self.debug(f"`-> took {round(time.time() - t, 2)} s")
            
            # PART-I: Q1.4: min average waiting time in minutes (over last hour)
            self.debug(f"computing min. average waiting time...")
            t = time.time()
            tmp = batch.orderBy(sf.asc("awt")).limit(1).select(batch.station, 
                                                               batch.awt.alias("min_awt"))
            self.kafka_session.createDataFrame(tmp.rdd).createOrReplaceTempView("min_awt")
            self.debug(f"`-> took {round(time.time() - t, 2)} s")
           
            # PART-I: Q1.5: max average waiting time in minutes (over last hour)
            self.debug(f"computing min. average waiting time...")
            t = time.time()
            tmp = batch.orderBy(sf.desc("awt")).limit(1).select(batch.station, 
                                                                batch.awt.alias("max_awt"))
            self.kafka_session.createDataFrame(tmp.rdd).createOrReplaceTempView("max_awt")
            self.debug(f"`-> took {round(time.time() - t, 2)} s")
                              
            self.debug(f"TSP:computeAwtMetrics successfully executed for batch #{batch_number}")
        except Exception as e:
            self.error(f"TSP:failed to compute awt metrics from batch #{batch_number}")
            self.error(e)                            
                       
    # -------------------------------------------------------------------------------    
    def computeTrainsProgressionAndSaveAsTempView(self, batch, batch_number):
    # -------------------------------------------------------------------------------
        # PART-II: COMPUTE TRAINS PROGRESSION
        # ------------------------------------
        # this 'forEachBatch' callback is attached to the our 'trprg_sink' (streaming query)
        try:    
            # clear cell content so that we don't cumulate the log               
            # self.clear_output()
                              
            # be sure we have some data to handle (incoming dataframe not empty)
            # this will avoid creating empty tables on Hive side 
            if batch.rdd.isEmpty():
                self.warning(f"TSP:computeTrainsProgression ignoring empty batch #{batch_number}")
                return

            t = time.time()

            # create next_departure 'lead' columns: departure columns up shifted by 1 row
            tmp = batch.withColumn('next_departure', sf.lead('departure') \
                       .over(spark_window.partitionBy("train") \
                       .orderBy("departure")))
            # create next_station 'lead' columns: station columns up shifted by 1 row
            tmp = tmp.withColumn('next_station', sf.lead('station') \
                     .over(spark_window.partitionBy("train") \
                     .orderBy("departure")))
            # create humanly readable columns for departure date/time 
            tmp = tmp.withColumn("departure_date", sf.from_unixtime(tmp.departure, "HH:mm:ss"))
            tmp = tmp.withColumn("next_departure_date", sf.from_unixtime(tmp.next_departure, "HH:mm:ss"))

            # compute travel time between 'departure' and 'next_departure' - i.e. from one station to the next
            tmp = tmp.withColumn("time_to_st", tmp.next_departure -  tmp.departure)
                       
            # travel direction encoding: 1:paris->banlieue or -1:banlieue->paris
            tmp = tmp.withColumn("direction", 
                                 sf.when(tmp.mission.isin(self.config['missions_to_paris']), sf.lit(1)) \
                                   .otherwise(sf.lit(-1)))
                       
            # swap departure date/time (due to train direction) - this is just for readability & display 
            tmp = tmp.withColumn("temp_departure_date", tmp.departure_date)
            tmp = tmp.withColumn("departure_date", 
                                 sf.when(tmp.departure < tmp.next_departure, tmp.departure_date) \
                                   .otherwise(tmp.next_departure_date))
            tmp = tmp.withColumn("next_departure_date", 
                                 sf.when(tmp.departure < tmp.next_departure, tmp.next_departure_date) \
                                   .otherwise(tmp.temp_departure_date))
            tmp = tmp.drop("temp_departure_date")

            # tmp.show()

            # create column to store the current time (i.e. now)
            tmp = tmp.withColumn("now", sf.unix_timestamp(sf.current_timestamp()))

            # the travel (from one station to the next) can belong to the past, the future or can be in progress 
            tmp = tmp.withColumn("in_past", (tmp.now > tmp.departure) & (tmp.now > tmp.next_departure))
            tmp = tmp.withColumn("in_future", (tmp.now < tmp.departure) & (tmp.now < tmp.next_departure))
            tmp = tmp.withColumn("in_progress", (tmp.in_past != sf.lit(True)) & (tmp.in_future != sf.lit(True)))

            # tmp.show()

            # keep only 'in progress' travels - i.e. the ones not in past nor in the future
            # we also remove: 
            #    - rows for which next_departure is null (introduced by the lead function)
            # note that we keep:
            #    - trains in standby (i.e fake travel from one station to the same - train waiting for next departure)
            tmp = tmp.filter((~tmp.in_past & ~tmp.in_future) & (tmp.next_departure.isNotNull()))

            # tmp.show()

            # compute travel progression in %
            tmp = tmp.withColumn("progress", (100. * sf.abs((tmp.now - tmp.departure))) / sf.abs(tmp.time_to_st))  
            # compute trains progression: maintain value in  the [O, 100]% range 
            tmp = tmp.withColumn("progress", sf.when(tmp.progress < sf.lit(0.), sf.lit(0.)).otherwise(tmp.progress))             
            # compute trains progression: maintain value in  the [O, 100]% range 
            tmp = tmp.withColumn("progress", sf.when(tmp.progress > sf.lit(100.), sf.lit(100.)).otherwise(tmp.progress))

            # tmp.show()
              
            # select the required columns
            tmp = tmp.select(tmp.train, 
                             tmp.departure_date.alias("departure"),
                             tmp.next_departure_date.alias("arrival"),
                             tmp.departure.alias("departure_uts"),
                             tmp.next_departure.alias("arrival_uts"),
                             tmp.mission, 
                             tmp.station.alias("from_st"), 
                             tmp.next_station.alias("to_st"), 
                             tmp.time_to_st,
                             tmp.progress,
                             tmp.direction) 
    
            # from (departure location)
            tmp = tmp.join(self.stations_data, tmp.from_st == self.stations_data.station, how="left")
            tmp = tmp.withColumn("from_st_lt", tmp.latitude).drop("latitude")
            tmp = tmp.withColumn("from_st_lg", tmp.longitude).drop("longitude")
            tmp = tmp.withColumn("from_st_lb", tmp.label).drop("label")
            tmp = tmp.drop("station")

            # to (destination location) 
            tmp = tmp.join(self.stations_data, tmp.to_st == self.stations_data.station, how="left")
            tmp = tmp.withColumn("to_st_lt", tmp.latitude).drop("latitude")
            tmp = tmp.withColumn("to_st_lg", tmp.longitude).drop("longitude")
            tmp = tmp.withColumn("to_st_lb", tmp.label).drop("label")
            tmp = tmp.drop("station")

            # compute current train latitude & longitude
            tmp = tmp.withColumn("train_lt", 
                                 tmp.from_st_lt + ((tmp.progress / 100.) * (tmp.to_st_lt - tmp.from_st_lt)))
            tmp = tmp.withColumn("train_lg", 
                                 tmp.from_st_lg + ((tmp.progress / 100.) * (tmp.to_st_lg - tmp.from_st_lg)))
              
            # cast progress to int
            tmp = tmp.withColumn("progress", sf.format_number(tmp.progress, 1).cast("double"))
            
            # compute accurate latitute and longitude using our user defined functions (udf)
            if self.accurate_trains_position_enabled:
                tmp = tmp.withColumn("train_alt", 
                                     TransilienStreamProcessor.alt_udf(tmp.from_st, tmp.to_st, tmp.progress))
                tmp = tmp.withColumn("train_alg", 
                                     TransilienStreamProcessor.alg_udf(tmp.from_st, tmp.to_st, tmp.progress))
            else:
                tmp = tmp.withColumn("train_alt", tmp.train_lt)
                tmp = tmp.withColumn("train_alg", tmp.train_lg)
                       
            # remove tmp data from table
            tmp = tmp.select("train",         # train identifier 
                             "departure",     # departure time
                             "arrival",       # arrival times
                             "departure_uts", # departure time as a unix timestamp (epoch)  
                             "arrival_uts",   # arrival time as a unix timestamp (epoch)   
                             "mission",       # mission code
                             "from_st",       # departure station code
                             "to_st",         # arrival station code
                             "from_st_lb",    # departure station label
                             "to_st_lb",      # arrival station label
                             "time_to_st",    # time_to_st = arrival - departure in seconds
                             "progress",      # travel progress
                             "direction",     # 1: paris -> banlieue, -1: banlieue->paris
                             "train_lt",      # coarce train location: latitude 
                             "train_lg",      # coarce train location: longitude
                             "train_alt",     # accurate train location: latitude 
                             "train_alg")     # accurate train location: longitude
            
            # log/debug/validate...
            if self.show_trprg_table:
                tmp.show()

            # post data to our TrainsTracker (if it exits)
            if self.trains_tracker is not None:
                self.trains_tracker.handle_trains_data(tmp.toPandas())
                
            # create a temp. view that - visible from Tableau  
            self.kafka_session.createDataFrame(tmp.rdd).createOrReplaceTempView("trains_progression")
            
            self.debug(f"`-> took {round(time.time() - t, 2)} s")
                              
            self.debug(f"TSP:computeTrainsProgression successfully executed for batch #{batch_number}")
        except Exception as e:
            self.error(f"TSP:failed to compute trains progression from batch #{batch_number}")
            self.error(e)
            
    # ------------------------------------------------------------------------------- 
    def set_trains_tracker(self, trains_tracker):
    # -------------------------------------------------------------------------------
        assert(isinstance(trains_tracker, Task) or trains_tracker is None)
        self.trains_tracker = trains_tracker