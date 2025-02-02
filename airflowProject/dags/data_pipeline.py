from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

default_args = {
    "owner": "airflow",
    "start_date": datetime(2024, 2, 1),
}

dag = DAG(
    "meltano_etl",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
)

extract_load = BashOperator(
    task_id="extract_load",
    bash_command="cd /meltano/etl_project && meltano run tap-postgres target-jsonl",
    dag=dag,
)

extract_load
