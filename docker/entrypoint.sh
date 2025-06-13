#!/bin/bash

# Add diagnostic commands
echo "Current directory: $(pwd)"
echo "Listing /ragflow directory:"
ls -la /ragflow
echo "Listing Python environment:"
which python3
python3 -m pip list | grep gunicorn
echo "Checking virtual environment:"
ls -la /ragflow/.venv/bin/ || echo "Virtual env directory not found"

# Activate virtual environment
source /ragflow/.venv/bin/activate

# Only generate config from template if service_conf.yaml doesn't exist
if [ ! -f /ragflow/conf/service_conf.yaml ]; then
    echo "Generating service_conf.yaml from template..."
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Use eval to interpret the variable with default values
        eval "echo \"$line\"" >> /ragflow/conf/service_conf.yaml
    done < /ragflow/conf/service_conf.yaml.template
else
    echo "Using existing service_conf.yaml"
fi

/usr/sbin/nginx

export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/

PY=python3
if [[ -z "$WS" || $WS -lt 1 ]]; then
  WS=1
fi

function task_exe(){
    JEMALLOC_PATH=$(pkg-config --variable=libdir jemalloc)/libjemalloc.so
    while [ 1 -eq 1 ];do
      LD_PRELOAD=$JEMALLOC_PATH $PY rag/svr/task_executor.py $1;
    done
}

for ((i=0;i<WS;i++))
do
  task_exe  $i &
done

echo "Starting gunicorn..."
# Start gunicorn with error handling
if ! gunicorn -c gunicorn.conf.py "api.ragflow_server:create_app()"; then
    echo "Error: Gunicorn failed to start"
    exit 1
fi

# Keep the script running
wait
