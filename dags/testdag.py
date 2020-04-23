from airflow import DAG
from datetime import datetime

from airflow.contrib.operators.ssh_operator import SSHOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import ShortCircuitOperator

from operators.ssh_operators import TemplateToSFTPOperator, ShortCircuitSSHOperator

default_args = {
    'owner': 'Damien Ayers',

    'depends_on_past': False,
    'start_date': datetime(2020, 2, 1),
    'email': ['damien.ayers@ga.gov.au'],
}

dag = DAG(
    'testdag',
    default_args=default_args,
    catchup=False,
    schedule_interval=None,
    template_searchpath='/home/omad/airflow/dags/templates/'
)

with dag:

    foo = SSHOperator(
        ssh_conn_id='lpgs_gadi',
        task_id='foo',
        remote_host='gadi-dm.nci.org.au',
        command='env'
    )

    failing_task = ShortCircuitSSHOperator(
        task_id='failing_task',
        ssh_conn_id='lpgs_gadi',
        command='false'
    )
    should_be_skipped = DummyOperator(
        task_id='should_be_skipped'
    )
    passing_task = ShortCircuitSSHOperator(
        task_id='passing_task',
        ssh_conn_id='lpgs_gadi',
        command='true'
    )
    should_be_run = DummyOperator(
        task_id='should_be_run'
    )
    failing_task >> should_be_skipped
    passing_task >> should_be_run
    # foo = BashOperator(
    #     task_id='foo',
    #     bash_command="echo Input is: {{ dag_run.conf.hello }}"
    #
    # )
    # upload_template_var = TemplateToSFTPOperator(
    #     task_id='upload_template_var',
    #     ssh_conn_id='omad_localhost',
    #     remote_filepath='/home/omad/{{ ds }}test.txt',
    #     file_contents="testtemplate.jinja2",
    #     create_intermediate_dirs=False,
    #     file_mode=0o644,
    # )
