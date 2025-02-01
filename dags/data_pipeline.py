from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime
import os
import psycopg2
import csv

default_args = {
    'start_date': datetime(2025, 1, 1),
    'retries': 1,  # Retry the tasks if they fail
}

def extract_table(table, ds, **kwargs):
    conn = psycopg2.connect(host='db', dbname='northwind', user='northwind_user', password='thewindisblowing')
    cur = conn.cursor()
    cur.execute(f'SELECT * FROM {table}')
    rows = cur.fetchall()
    os.makedirs(f'/opt/airflow/data/postgres/{table}/{ds}', exist_ok=True)
    with open(f'/opt/airflow/data/postgres/{table}/{ds}/{table}.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([desc[0] for desc in cur.description])
        writer.writerows(rows)
    cur.close()
    conn.close()

def extract_orders(ds, **kwargs):
    extract_table('orders', ds, **kwargs)

def extract_customers(ds, **kwargs):
    extract_table('customers', ds, **kwargs)

def copy_order_details(ds, **kwargs):
    os.makedirs(f'/opt/airflow/data/csv/{ds}', exist_ok=True)
    os.system(f'cp /opt/airflow/data/order_details.csv /opt/airflow/data/csv/{ds}/order_details.csv')

def verify_pipeline(ds, **kwargs):
    conn = psycopg2.connect(host='db', dbname='northwind', user='northwind_user', password='thewindisblowing')
    cur = conn.cursor()
    cur.execute('SELECT o.order_id, o.order_date, d.product_id, d.quantity FROM orders o JOIN order_details_final d ON o.order_id = d.order_id')
    rows = cur.fetchall()
    os.makedirs(f'/opt/airflow/data/results/{ds}', exist_ok=True)
    with open(f'/opt/airflow/data/results/{ds}/result.json', 'w') as f:
        import json
        json.dump(rows, f)
    cur.close()
    conn.close()

with DAG('data_pipeline', default_args=default_args, schedule_interval='@daily', catchup=True) as dag:
    extract_orders_task = PythonOperator(task_id='extract_orders', python_callable=extract_orders)
    extract_customers_task = PythonOperator(task_id='extract_customers', python_callable=extract_customers)
    extract_order_details_task = PythonOperator(task_id='extract_order_details', python_callable=copy_order_details)
    load_orders_task = BashOperator(
        task_id='load_orders',
        bash_command='meltano run tap-csv target-postgres --config /opt/airflow/dags/meltano_orders.yml > /opt/airflow/logs/load_orders.log 2>&1'
    )

    load_order_details_task = BashOperator(
        task_id='load_order_details',
        bash_command='meltano run tap-csv target-postgres --config /opt/airflow/dags/meltano_order_details.yml > /opt/airflow/logs/load_order_details.log 2>&1'
    )

    verify_task = PythonOperator(task_id='verify', python_callable=verify_pipeline)

    # Task dependencies
    extract_orders_task >> [load_orders_task, load_order_details_task] >> verify_task
    extract_customers_task >> [load_orders_task, load_order_details_task] >> verify_task
    extract_order_details_task >> [load_orders_task, load_order_details_task] >> verify_task
