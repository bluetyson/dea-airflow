"""DAG to periodically/one-shot update explorer and ows schemas in RDS
after a given Dataset has been indexed from S3.
- Run Explorer summaries
- Run ows update ranges for NRT products
- Run ows update ranges for NRT multi-products

This DAG uses k8s executors and pre-existing pods in cluster with relevant tooling
and configuration installed

set start_date to something real, not datetime.utcnow() because that'll break things

for setting upstream and downstream, use
start >> passing
start >> failing

You can use `with dag: ` as a context manager, and not have to manually pass it as an argument
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.contrib.operators.kubernetes_pod_operator import KubernetesPodOperator
from airflow.contrib.kubernetes.secret import Secret
from airflow.operators.dummy_operator import DummyOperator


DEFAULT_ARGS = {
    "owner": "Tisham Dhar",
    "depends_on_past": False,
    "start_date": datetime(2020, 3, 4),
    "email": ["tisham.dhar@ga.gov.au"],
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "env_vars": {
        "AWS_DEFAULT_REGION": "ap-southeast-2",
        # TODO: Pass these via templated params in DAG Run
        "DB_HOSTNAME": "database.local",
        "DB_DATABASE": "ows-index",
    },
    # Use K8S secrets to send DB Creds
    # Lift secrets into environment variables for datacube
    "secrets": [
        Secret("env", "DB_USERNAME", "ows-db", "postgres-username"),
        Secret("env", "DB_PASSWORD", "ows-db", "postgres-password"),
    ],
}

INDEXER_IMAGE = "opendatacube/datacube-index:v0.0.3"
OWS_IMAGE = "opendatacube/ows:0.13.3-unstable.5.g86139b5"
EXPLORER_IMAGE = "opendatacube/dashboard:2.1.6"

dag = DAG(
    "k8s_s3_orchestrate",
    default_args=DEFAULT_ARGS,
    schedule_interval=None,
    catchup=False,
    tags=["k8s"]
)


with dag:
    START = DummyOperator(task_id="s3_index_publish")

    # TODO: Bootstrap if targeting a Blank DB
    # TODO: Initialize Datacube
    # TODO: Add metadata types
    # TODO: Add products
    BOOTSTRAP = KubernetesPodOperator(
        namespace="processing",
        image=INDEXER_IMAGE,
        cmds=["datacube", "system", "check"],
        labels={"step": "bootstrap"},
        name="odc-bootstrap",
        task_id="bootstrap-task",
        get_logs=True,
    )

    INDEXING = KubernetesPodOperator(
        namespace="processing",
        image=INDEXER_IMAGE,
        cmds=["s3-to-dc"],
        # Assume kube2iam role via annotations
        # TODO: Pass this via DAG parameters
        annotations={"iam.amazonaws.com/role": "dea-dev-eks-wms"},
        # TODO: Collect form JSON used to trigger DAG
        arguments=[
            # "s3://dea-public-data/cemp_insar/insar/displacement/alos//**/*.yaml",
            # "cemp_insar_alos_displacement",
            # Jinja templates for arguments
            "{{ dag_run.conf.s3_glob }}",
            "{{ dag_run.conf.product }}"
        ],
        labels={"step": "s3-to-rds"},
        name="datacube-index",
        task_id="indexing-task",
        get_logs=True,
    )

    UPDATE_RANGES = KubernetesPodOperator(
        namespace="processing",
        image=OWS_IMAGE,
        cmds=["datacube-ows-update"],
        arguments=["--help"],
        labels={"step": "ows"},
        name="ows-update-ranges",
        task_id="update-ranges-task",
        get_logs=True,
    )

    SUMMARY = KubernetesPodOperator(
        namespace="processing",
        image=EXPLORER_IMAGE,
        cmds=["cubedash-gen"],
        arguments=["--help"],
        labels={"step": "explorer"},
        name="explorer-summary",
        task_id="explorer-summary-task",
        get_logs=True,
    )

    COMPLETE = DummyOperator(task_id="all_done")

    START >> BOOTSTRAP
    BOOTSTRAP >> INDEXING
    INDEXING >> UPDATE_RANGES
    INDEXING >> SUMMARY
    UPDATE_RANGES >> COMPLETE
    SUMMARY >> COMPLETE
