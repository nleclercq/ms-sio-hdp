export SPARK_HOME=/root/miniconda3/lib/python3.7/site-packages/pyspark
source "${SPARK_HOME}"/bin/load-spark-env.sh
export PYTHONPATH="${SPARK_HOME}/python/:$PYTHONPATH"
export PYTHONPATH="${SPARK_HOME}/python/lib/py4j-0.10.7-src.zip:$PYTHONPATH"
export HADOOP_CONF_DIR=/etc/hadoop/conf
export YARN_CONF_DIR=/etc/hadoop/conf
export JAVA_HOME=/usr/lib/jvm/jre-1.8.0-openjdk
export JRE_HOME=/usr/lib/jvm/jre-1.8.0-openjdk/jre
export PYSPARK_PYTHON=python3
export PATH=$SPARK_HOME:$JAVA_HOME/bin:$JAVA_HOME/jre/bin:$PATH
export PYTHONSTARTUP="${SPARK_HOME}/python/pyspark/shell.py"

spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.11:2.4.0 ./api-transilien-consumer.py
