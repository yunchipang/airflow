#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from copy import deepcopy
from datetime import date, time
from unittest import mock

import pytest
import time_machine
from botocore.credentials import Credentials

from airflow.exceptions import AirflowException, TaskDeferred
from airflow.providers.google.cloud.hooks.cloud_storage_transfer_service import (
    ACCESS_KEY_ID,
    AWS_ACCESS_KEY,
    AWS_ROLE_ARN,
    AWS_S3_DATA_SOURCE,
    BUCKET_NAME,
    FILTER_JOB_NAMES,
    GCS_DATA_SINK,
    GCS_DATA_SOURCE,
    HTTP_DATA_SOURCE,
    LIST_URL,
    NAME,
    PATH,
    SCHEDULE,
    SCHEDULE_END_DATE,
    SCHEDULE_START_DATE,
    SECRET_ACCESS_KEY,
    START_TIME_OF_DAY,
    STATUS,
    TRANSFER_SPEC,
)
from airflow.providers.google.cloud.operators.cloud_storage_transfer_service import (
    CloudDataTransferServiceCancelOperationOperator,
    CloudDataTransferServiceCreateJobOperator,
    CloudDataTransferServiceDeleteJobOperator,
    CloudDataTransferServiceGCSToGCSOperator,
    CloudDataTransferServiceGetOperationOperator,
    CloudDataTransferServiceListOperationsOperator,
    CloudDataTransferServicePauseOperationOperator,
    CloudDataTransferServiceResumeOperationOperator,
    CloudDataTransferServiceRunJobOperator,
    CloudDataTransferServiceS3ToGCSOperator,
    CloudDataTransferServiceUpdateJobOperator,
    TransferJobPreprocessor,
    TransferJobValidator,
)
from airflow.providers.google.cloud.triggers.cloud_storage_transfer_service import (
    CloudStorageTransferServiceCheckJobStatusTrigger,
)
from airflow.utils import timezone

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None

GCP_PROJECT_ID = "project-id"
TASK_ID = "task-id"
IMPERSONATION_CHAIN = ["ACCOUNT_1", "ACCOUNT_2", "ACCOUNT_3"]

JOB_NAME = "job-name/job-name"
OPERATION_NAME = "transferOperations/transferJobs-123-456"
AWS_BUCKET_NAME = "aws-bucket-name"
GCS_BUCKET_NAME = "gcp-bucket-name"
AWS_ROLE_ARN_INPUT = "aRoleARn"
SOURCE_PATH = None
DESTINATION_PATH = None
DESCRIPTION = "description"

DEFAULT_DATE = timezone.datetime(2017, 1, 1)

TEST_FILTER = {FILTER_JOB_NAMES: [JOB_NAME]}

TEST_AWS_ACCESS_KEY_ID = "test-key-1"
TEST_AWS_ACCESS_SECRET = "test-secret-1"
TEST_AWS_ACCESS_KEY = {ACCESS_KEY_ID: TEST_AWS_ACCESS_KEY_ID, SECRET_ACCESS_KEY: TEST_AWS_ACCESS_SECRET}

NATIVE_DATE = date(2018, 10, 15)
DICT_DATE = {"day": 15, "month": 10, "year": 2018}
NATIVE_TIME = time(hour=11, minute=42, second=43)
DICT_TIME = {"hours": 11, "minutes": 42, "seconds": 43}
SCHEDULE_NATIVE = {
    SCHEDULE_START_DATE: NATIVE_DATE,
    SCHEDULE_END_DATE: NATIVE_DATE,
    START_TIME_OF_DAY: NATIVE_TIME,
}

SCHEDULE_DICT = {
    SCHEDULE_START_DATE: {"day": 15, "month": 10, "year": 2018},
    SCHEDULE_END_DATE: {"day": 15, "month": 10, "year": 2018},
    START_TIME_OF_DAY: {"hours": 11, "minutes": 42, "seconds": 43},
}

SOURCE_AWS = {AWS_S3_DATA_SOURCE: {BUCKET_NAME: AWS_BUCKET_NAME, PATH: SOURCE_PATH}}
SOURCE_AWS_ROLE_ARN = {
    AWS_S3_DATA_SOURCE: {BUCKET_NAME: AWS_BUCKET_NAME, PATH: SOURCE_PATH, AWS_ROLE_ARN: AWS_ROLE_ARN_INPUT}
}
SOURCE_GCS = {GCS_DATA_SOURCE: {BUCKET_NAME: GCS_BUCKET_NAME, PATH: SOURCE_PATH}}
SOURCE_HTTP = {HTTP_DATA_SOURCE: {LIST_URL: "http://example.com"}}

VALID_TRANSFER_JOB_BASE: dict = {
    NAME: JOB_NAME,
    DESCRIPTION: DESCRIPTION,
    STATUS: "ENABLED",
    SCHEDULE: SCHEDULE_DICT,
    TRANSFER_SPEC: {GCS_DATA_SINK: {BUCKET_NAME: GCS_BUCKET_NAME, PATH: DESTINATION_PATH}},
}
VALID_TRANSFER_JOB_JINJA = deepcopy(VALID_TRANSFER_JOB_BASE)
VALID_TRANSFER_JOB_JINJA[NAME] = "{{ dag.dag_id }}"
VALID_TRANSFER_JOB_JINJA_RENDERED = deepcopy(VALID_TRANSFER_JOB_JINJA)
VALID_TRANSFER_JOB_JINJA_RENDERED[NAME] = "TestGcpStorageTransferJobCreateOperator"
VALID_TRANSFER_JOB_GCS = deepcopy(VALID_TRANSFER_JOB_BASE)
VALID_TRANSFER_JOB_GCS[TRANSFER_SPEC].update(deepcopy(SOURCE_GCS))
VALID_TRANSFER_JOB_AWS = deepcopy(VALID_TRANSFER_JOB_BASE)
VALID_TRANSFER_JOB_AWS[TRANSFER_SPEC].update(deepcopy(SOURCE_AWS))
VALID_TRANSFER_JOB_AWS_ROLE_ARN = deepcopy(VALID_TRANSFER_JOB_BASE)
VALID_TRANSFER_JOB_AWS_ROLE_ARN[TRANSFER_SPEC].update(deepcopy(SOURCE_AWS_ROLE_ARN))

VALID_TRANSFER_JOB_GCS = {
    NAME: JOB_NAME,
    DESCRIPTION: DESCRIPTION,
    STATUS: "ENABLED",
    SCHEDULE: SCHEDULE_NATIVE,
    TRANSFER_SPEC: {
        GCS_DATA_SOURCE: {BUCKET_NAME: GCS_BUCKET_NAME, PATH: SOURCE_PATH},
        GCS_DATA_SINK: {BUCKET_NAME: GCS_BUCKET_NAME, PATH: DESTINATION_PATH},
    },
}

VALID_TRANSFER_JOB_RAW: dict = {
    DESCRIPTION: DESCRIPTION,
    STATUS: "ENABLED",
    SCHEDULE: SCHEDULE_DICT,
    TRANSFER_SPEC: {GCS_DATA_SINK: {BUCKET_NAME: GCS_BUCKET_NAME, PATH: DESTINATION_PATH}},
}

VALID_TRANSFER_JOB_GCS_RAW = deepcopy(VALID_TRANSFER_JOB_RAW)
VALID_TRANSFER_JOB_GCS_RAW[TRANSFER_SPEC].update(SOURCE_GCS)
VALID_TRANSFER_JOB_AWS_RAW = deepcopy(VALID_TRANSFER_JOB_RAW)
VALID_TRANSFER_JOB_AWS_RAW[TRANSFER_SPEC].update(deepcopy(SOURCE_AWS))
VALID_TRANSFER_JOB_AWS_RAW[TRANSFER_SPEC][AWS_S3_DATA_SOURCE][AWS_ACCESS_KEY] = TEST_AWS_ACCESS_KEY
VALID_TRANSFER_JOB_AWS_WITH_ROLE_ARN_RAW = deepcopy(VALID_TRANSFER_JOB_RAW)
VALID_TRANSFER_JOB_AWS_WITH_ROLE_ARN_RAW[TRANSFER_SPEC].update(deepcopy(SOURCE_AWS_ROLE_ARN))
VALID_TRANSFER_JOB_AWS_WITH_ROLE_ARN_RAW[TRANSFER_SPEC][AWS_S3_DATA_SOURCE][AWS_ROLE_ARN] = AWS_ROLE_ARN_INPUT

VALID_OPERATION = {NAME: "operation-name"}


class TestTransferJobPreprocessor:
    def test_should_do_nothing_on_empty(self):
        body = {}
        TransferJobPreprocessor(body=body).process_body()
        assert body == {}

    @pytest.mark.skipif(boto3 is None, reason="Skipping test because boto3 is not available")
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_should_inject_aws_credentials(self, mock_hook):
        mock_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        body = {TRANSFER_SPEC: deepcopy(SOURCE_AWS)}
        body = TransferJobPreprocessor(body=body).process_body()
        assert body[TRANSFER_SPEC][AWS_S3_DATA_SOURCE][AWS_ACCESS_KEY] == TEST_AWS_ACCESS_KEY

    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_should_not_inject_aws_credentials(self, mock_hook):
        mock_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        body = {TRANSFER_SPEC: deepcopy(SOURCE_AWS_ROLE_ARN)}
        body = TransferJobPreprocessor(body=body).process_body()
        assert AWS_ACCESS_KEY not in body[TRANSFER_SPEC][AWS_S3_DATA_SOURCE]

    @pytest.mark.parametrize("field_attr", [SCHEDULE_START_DATE, SCHEDULE_END_DATE])
    def test_should_format_date_from_python_to_dict(self, field_attr):
        body = {SCHEDULE: {field_attr: NATIVE_DATE}}
        TransferJobPreprocessor(body=body).process_body()
        assert body[SCHEDULE][field_attr] == DICT_DATE

    def test_should_format_time_from_python_to_dict(self):
        body = {SCHEDULE: {START_TIME_OF_DAY: NATIVE_TIME}}
        TransferJobPreprocessor(body=body).process_body()
        assert body[SCHEDULE][START_TIME_OF_DAY] == DICT_TIME

    @pytest.mark.parametrize("field_attr", [SCHEDULE_START_DATE, SCHEDULE_END_DATE])
    def test_should_not_change_date_for_dict(self, field_attr):
        body = {SCHEDULE: {field_attr: DICT_DATE}}
        TransferJobPreprocessor(body=body).process_body()
        assert body[SCHEDULE][field_attr] == DICT_DATE

    def test_should_not_change_time_for_dict(self):
        body = {SCHEDULE: {START_TIME_OF_DAY: DICT_TIME}}
        TransferJobPreprocessor(body=body).process_body()
        assert body[SCHEDULE][START_TIME_OF_DAY] == DICT_TIME

    @time_machine.travel("2018-10-15", tick=False)
    def test_should_set_default_schedule(self):
        body = {}
        TransferJobPreprocessor(body=body, default_schedule=True).process_body()
        assert body == {
            SCHEDULE: {
                SCHEDULE_END_DATE: {"day": 15, "month": 10, "year": 2018},
                SCHEDULE_START_DATE: {"day": 15, "month": 10, "year": 2018},
            }
        }


class TestTransferJobValidator:
    def test_should_raise_exception_when_encounters_aws_credentials(self):
        body = {"transferSpec": {"awsS3DataSource": {"awsAccessKey": TEST_AWS_ACCESS_KEY}}}
        with pytest.raises(AirflowException) as ctx:
            TransferJobValidator(body=body).validate_body()
        err = ctx.value
        assert (
            "AWS credentials detected inside the body parameter (awsAccessKey). This is not allowed, please "
            "use Airflow connections to store credentials." in str(err)
        )

    def test_should_raise_exception_when_body_empty(self):
        body = None
        with pytest.raises(AirflowException) as ctx:
            TransferJobValidator(body=body).validate_body()
        err = ctx.value
        assert "The required parameter 'body' is empty or None" in str(err)

    @pytest.mark.parametrize(
        "transfer_spec",
        [
            {**SOURCE_AWS, **SOURCE_GCS, **SOURCE_HTTP},
            {**SOURCE_AWS, **SOURCE_GCS},
            {**SOURCE_AWS, **SOURCE_HTTP},
            {**SOURCE_GCS, **SOURCE_HTTP},
        ],
    )
    def test_verify_data_source(self, transfer_spec):
        body = {TRANSFER_SPEC: transfer_spec}

        with pytest.raises(AirflowException) as ctx:
            TransferJobValidator(body=body).validate_body()
        err = ctx.value
        assert (
            "More than one data source detected. Please choose exactly one data source from: "
            "gcsDataSource, awsS3DataSource and httpDataSource." in str(err)
        )

    @pytest.mark.parametrize(
        "body", [VALID_TRANSFER_JOB_GCS, VALID_TRANSFER_JOB_AWS, VALID_TRANSFER_JOB_AWS_ROLE_ARN]
    )
    def test_verify_success(self, body):
        try:
            TransferJobValidator(body=body).validate_body()
            validated = True
        except AirflowException:
            validated = False

        assert validated


class TestGcpStorageTransferJobCreateOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_create_gcs(self, mock_hook):
        mock_hook.return_value.create_transfer_job.return_value = VALID_TRANSFER_JOB_GCS
        body = deepcopy(VALID_TRANSFER_JOB_GCS)
        del body["name"]
        op = CloudDataTransferServiceCreateJobOperator(
            body=body,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(context=mock.MagicMock())

        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )

        mock_hook.return_value.create_transfer_job.assert_called_once_with(body=VALID_TRANSFER_JOB_GCS_RAW)

        assert result == VALID_TRANSFER_JOB_GCS

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_job_create_aws(self, aws_hook, mock_hook):
        mock_hook.return_value.create_transfer_job.return_value = VALID_TRANSFER_JOB_AWS
        aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )
        body = deepcopy(VALID_TRANSFER_JOB_AWS)
        del body["name"]
        op = CloudDataTransferServiceCreateJobOperator(
            body=body,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )

        result = op.execute(context=mock.MagicMock())

        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )

        mock_hook.return_value.create_transfer_job.assert_called_once_with(body=VALID_TRANSFER_JOB_AWS_RAW)

        assert result == VALID_TRANSFER_JOB_AWS

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_job_create_aws_with_role_arn(self, aws_hook, mock_hook):
        mock_hook.return_value.create_transfer_job.return_value = VALID_TRANSFER_JOB_AWS_ROLE_ARN
        body = deepcopy(VALID_TRANSFER_JOB_AWS_ROLE_ARN)
        del body["name"]
        op = CloudDataTransferServiceCreateJobOperator(
            body=body,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )

        result = op.execute(context=mock.MagicMock())

        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )

        mock_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_AWS_WITH_ROLE_ARN_RAW
        )

        assert result == VALID_TRANSFER_JOB_AWS_ROLE_ARN

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_job_create_multiple(self, aws_hook, gcp_hook):
        aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )
        gcp_hook.return_value.create_transfer_job.return_value = VALID_TRANSFER_JOB_AWS
        body = deepcopy(VALID_TRANSFER_JOB_AWS)

        op = CloudDataTransferServiceCreateJobOperator(body=body, task_id=TASK_ID)
        result = op.execute(context=mock.MagicMock())
        assert result == VALID_TRANSFER_JOB_AWS

        op = CloudDataTransferServiceCreateJobOperator(body=body, task_id=TASK_ID)
        result = op.execute(context=mock.MagicMock())
        assert result == VALID_TRANSFER_JOB_AWS

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @pytest.mark.parametrize(
        "body, excepted",
        [(VALID_TRANSFER_JOB_JINJA, VALID_TRANSFER_JOB_JINJA_RENDERED)],
    )
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_templates(self, _, create_task_instance_of_operator, body, excepted, session):
        dag_id = "TestGcpStorageTransferJobCreateOperator"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceCreateJobOperator,
            dag_id=dag_id,
            body=body,
            gcp_conn_id="{{ dag.dag_id }}",
            aws_conn_id="{{ dag.dag_id }}",
            task_id="task-id",
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert excepted == getattr(ti.task, "body")
        assert dag_id == getattr(ti.task, "gcp_conn_id")
        assert dag_id == getattr(ti.task, "aws_conn_id")


class TestGcpStorageTransferJobUpdateOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_update(self, mock_hook):
        mock_hook.return_value.update_transfer_job.return_value = VALID_TRANSFER_JOB_GCS
        body = {"transferJob": {"description": "example-name"}, "updateTransferJobFieldMask": DESCRIPTION}

        op = CloudDataTransferServiceUpdateJobOperator(
            job_name=JOB_NAME,
            body=body,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(context=mock.MagicMock())

        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.update_transfer_job.assert_called_once_with(job_name=JOB_NAME, body=body)
        assert result == VALID_TRANSFER_JOB_GCS

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "TestGcpStorageTransferJobUpdateOperator_test_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceUpdateJobOperator,
            dag_id=dag_id,
            job_name="{{ dag.dag_id }}",
            body={"transferJob": {"name": "{{ dag.dag_id }}"}},
            task_id="task-id",
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == getattr(ti.task, "body")["transferJob"]["name"]
        assert dag_id == getattr(ti.task, "job_name")


class TestGcpStorageTransferJobDeleteOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_delete(self, mock_hook):
        op = CloudDataTransferServiceDeleteJobOperator(
            job_name=JOB_NAME,
            project_id=GCP_PROJECT_ID,
            task_id="task-id",
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        op.execute(None)
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.delete_transfer_job.assert_called_once_with(
            job_name=JOB_NAME, project_id=GCP_PROJECT_ID
        )

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_delete_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_job_delete_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceDeleteJobOperator,
            dag_id=dag_id,
            job_name="{{ dag.dag_id }}",
            gcp_conn_id="{{ dag.dag_id }}",
            api_version="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.job_name
        assert dag_id == ti.task.gcp_conn_id
        assert dag_id == ti.task.api_version

    def test_job_delete_should_throw_ex_when_name_none(self):
        with pytest.raises(AirflowException, match="The required parameter 'job_name' is empty or None"):
            CloudDataTransferServiceDeleteJobOperator(job_name="", task_id="task-id")


class TestGcpStorageTransferJobRunOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_run(self, mock_hook):
        mock_hook.return_value.run_transfer_job.return_value = VALID_OPERATION
        op = CloudDataTransferServiceRunJobOperator(
            job_name=JOB_NAME,
            project_id=GCP_PROJECT_ID,
            task_id="task-id",
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(context=mock.MagicMock())
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.run_transfer_job.assert_called_once_with(
            job_name=JOB_NAME, project_id=GCP_PROJECT_ID
        )
        assert result == VALID_OPERATION

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_job_run_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_job_run_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceRunJobOperator,
            dag_id=dag_id,
            job_name="{{ dag.dag_id }}",
            project_id="{{ dag.dag_id }}",
            gcp_conn_id="{{ dag.dag_id }}",
            api_version="{{ dag.dag_id }}",
            google_impersonation_chain="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.job_name
        assert dag_id == ti.task.project_id
        assert dag_id == ti.task.gcp_conn_id
        assert dag_id == ti.task.api_version
        assert dag_id == ti.task.google_impersonation_chain

    def test_job_run_should_throw_ex_when_name_none(self):
        op = CloudDataTransferServiceRunJobOperator(job_name="", task_id="task-id")
        with pytest.raises(AirflowException, match="The required parameter 'job_name' is empty or None"):
            op.execute(context=mock.MagicMock())


class TestGpcStorageTransferOperationsGetOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_get(self, mock_hook):
        mock_hook.return_value.get_transfer_operation.return_value = VALID_OPERATION
        op = CloudDataTransferServiceGetOperationOperator(
            operation_name=OPERATION_NAME,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(context=mock.MagicMock())
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.get_transfer_operation.assert_called_once_with(operation_name=OPERATION_NAME)
        assert result == VALID_OPERATION

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_get_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_operation_get_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceGetOperationOperator,
            dag_id=dag_id,
            operation_name="{{ dag.dag_id }}",
            task_id="task-id",
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.operation_name

    def test_operation_get_should_throw_ex_when_operation_name_none(self):
        with pytest.raises(
            AirflowException, match="The required parameter 'operation_name' is empty or None"
        ):
            CloudDataTransferServiceGetOperationOperator(operation_name="", task_id=TASK_ID)


class TestGcpStorageTransferOperationListOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_list(self, mock_hook):
        mock_hook.return_value.list_transfer_operations.return_value = [VALID_TRANSFER_JOB_GCS]
        op = CloudDataTransferServiceListOperationsOperator(
            request_filter=TEST_FILTER,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(context=mock.MagicMock())
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.list_transfer_operations.assert_called_once_with(request_filter=TEST_FILTER)
        assert result == [VALID_TRANSFER_JOB_GCS]

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "TestGcpStorageTransferOperationListOperator_test_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceListOperationsOperator,
            dag_id=dag_id,
            request_filter={"job_names": ["{{ dag.dag_id }}"]},
            gcp_conn_id="{{ dag.dag_id }}",
            task_id="task-id",
        )
        session.add(ti)
        session.commit()
        ti.render_templates()

        assert dag_id == ti.task.request_filter["job_names"][0]
        assert dag_id == ti.task.gcp_conn_id


class TestGcpStorageTransferOperationsPauseOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_pause(self, mock_hook):
        op = CloudDataTransferServicePauseOperationOperator(
            operation_name=OPERATION_NAME,
            task_id="task-id",
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        op.execute(None)
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.pause_transfer_operation.assert_called_once_with(operation_name=OPERATION_NAME)

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_pause_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_operation_pause_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServicePauseOperationOperator,
            dag_id=dag_id,
            operation_name="{{ dag.dag_id }}",
            gcp_conn_id="{{ dag.dag_id }}",
            api_version="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.operation_name
        assert dag_id == ti.task.gcp_conn_id
        assert dag_id == ti.task.api_version

    def test_operation_pause_should_throw_ex_when_name_none(self):
        with pytest.raises(
            AirflowException, match="The required parameter 'operation_name' is empty or None"
        ):
            CloudDataTransferServicePauseOperationOperator(operation_name="", task_id="task-id")


class TestGcpStorageTransferOperationsResumeOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_resume(self, mock_hook):
        op = CloudDataTransferServiceResumeOperationOperator(
            operation_name=OPERATION_NAME,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(None)
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.resume_transfer_operation.assert_called_once_with(
            operation_name=OPERATION_NAME
        )
        assert result is None

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_resume_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_operation_resume_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceResumeOperationOperator,
            dag_id=dag_id,
            operation_name="{{ dag.dag_id }}",
            gcp_conn_id="{{ dag.dag_id }}",
            api_version="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.operation_name
        assert dag_id == ti.task.gcp_conn_id
        assert dag_id == ti.task.api_version

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_resume_should_throw_ex_when_name_none(self, mock_hook):
        with pytest.raises(
            AirflowException, match="The required parameter 'operation_name' is empty or None"
        ):
            CloudDataTransferServiceResumeOperationOperator(operation_name="", task_id=TASK_ID)


class TestGcpStorageTransferOperationsCancelOperator:
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_cancel(self, mock_hook):
        op = CloudDataTransferServiceCancelOperationOperator(
            operation_name=OPERATION_NAME,
            task_id=TASK_ID,
            google_impersonation_chain=IMPERSONATION_CHAIN,
        )
        result = op.execute(None)
        mock_hook.assert_called_once_with(
            api_version="v1",
            gcp_conn_id="google_cloud_default",
            impersonation_chain=IMPERSONATION_CHAIN,
        )
        mock_hook.return_value.cancel_transfer_operation.assert_called_once_with(
            operation_name=OPERATION_NAME
        )
        assert result is None

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_cancel_with_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "test_operation_cancel_with_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceCancelOperationOperator,
            dag_id=dag_id,
            operation_name="{{ dag.dag_id }}",
            gcp_conn_id="{{ dag.dag_id }}",
            api_version="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.operation_name
        assert dag_id == ti.task.gcp_conn_id
        assert dag_id == ti.task.api_version

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_operation_cancel_should_throw_ex_when_name_none(self, mock_hook):
        with pytest.raises(
            AirflowException, match="The required parameter 'operation_name' is empty or None"
        ):
            CloudDataTransferServiceCancelOperationOperator(operation_name="", task_id=TASK_ID)


class TestS3ToGoogleCloudStorageTransferOperator:
    def test_constructor(self):
        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
        )

        assert operator.task_id == TASK_ID
        assert operator.s3_bucket == AWS_BUCKET_NAME
        assert operator.gcs_bucket == GCS_BUCKET_NAME
        assert operator.project_id == GCP_PROJECT_ID
        assert operator.description == DESCRIPTION
        assert operator.schedule == SCHEDULE_DICT

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "TestS3ToGoogleCloudStorageTransferOperator_test_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceS3ToGCSOperator,
            dag_id=dag_id,
            s3_bucket="{{ dag.dag_id }}",
            gcs_bucket="{{ dag.dag_id }}",
            description="{{ dag.dag_id }}",
            object_conditions={"exclude_prefixes": ["{{ dag.dag_id }}"]},
            gcp_conn_id="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.s3_bucket
        assert dag_id == ti.task.gcs_bucket
        assert dag_id == ti.task.description
        assert dag_id == ti.task.object_conditions["exclude_prefixes"][0]
        assert dag_id == ti.task.gcp_conn_id

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_execute(self, mock_aws_hook, mock_transfer_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_AWS_RAW
        )

        assert mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert not mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_execute_skip_wait(self, mock_aws_hook, mock_transfer_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            wait=False,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_AWS_RAW
        )

        assert not mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert not mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_execute_delete_job_after_completion(self, mock_aws_hook, mock_transfer_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            wait=True,
            delete_job_after_completion=True,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_AWS_RAW
        )

        assert mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_execute_should_throw_ex_when_delete_job_without_wait(self, mock_aws_hook, mock_transfer_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        with pytest.raises(
            AirflowException, match="If 'delete_job_after_completion' is True, then 'wait' must also be True."
        ):
            CloudDataTransferServiceS3ToGCSOperator(
                task_id=TASK_ID,
                s3_bucket=AWS_BUCKET_NAME,
                gcs_bucket=GCS_BUCKET_NAME,
                description=DESCRIPTION,
                schedule=SCHEDULE_DICT,
                wait=False,
                delete_job_after_completion=True,
            )

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_async_defer_successfully(self, mock_aws_hook, mock_transfer_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        with pytest.raises(TaskDeferred) as exc:
            operator.execute({})
        assert isinstance(exc.value.trigger, CloudStorageTransferServiceCheckJobStatusTrigger)

    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_async_execute_successfully(self, mock_aws_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        operator.execute_complete(context={}, event={"status": "success"})

    @mock.patch("airflow.providers.google.cloud.operators.cloud_storage_transfer_service.AwsBaseHook")
    def test_async_execute_error(self, mock_aws_hook):
        mock_aws_hook.return_value.get_credentials.return_value = Credentials(
            TEST_AWS_ACCESS_KEY_ID, TEST_AWS_ACCESS_SECRET, None
        )

        operator = CloudDataTransferServiceS3ToGCSOperator(
            task_id=TASK_ID,
            s3_bucket=AWS_BUCKET_NAME,
            gcs_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        with pytest.raises(AirflowException):
            operator.execute_complete(
                context={}, event={"status": "error", "message": "test failure message"}
            )


class TestGoogleCloudStorageToGoogleCloudStorageTransferOperator:
    def test_constructor(self):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
        )

        assert operator.task_id == TASK_ID
        assert operator.source_bucket == GCS_BUCKET_NAME
        assert operator.destination_bucket == GCS_BUCKET_NAME
        assert operator.project_id == GCP_PROJECT_ID
        assert operator.description == DESCRIPTION
        assert operator.schedule == SCHEDULE_DICT

    # Setting all the operator's input parameters as templated dag_ids
    # (could be anything else) just to test if the templating works for all
    # fields
    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_templates(self, _, create_task_instance_of_operator, session):
        dag_id = "TestGoogleCloudStorageToGoogleCloudStorageTransferOperator_test_templates"
        ti = create_task_instance_of_operator(
            CloudDataTransferServiceGCSToGCSOperator,
            dag_id=dag_id,
            source_bucket="{{ dag.dag_id }}",
            destination_bucket="{{ dag.dag_id }}",
            description="{{ dag.dag_id }}",
            object_conditions={"exclude_prefixes": ["{{ dag.dag_id }}"]},
            gcp_conn_id="{{ dag.dag_id }}",
            task_id=TASK_ID,
        )
        session.add(ti)
        session.commit()
        ti.render_templates()
        assert dag_id == ti.task.source_bucket
        assert dag_id == ti.task.destination_bucket
        assert dag_id == ti.task.description
        assert dag_id == ti.task.object_conditions["exclude_prefixes"][0]
        assert dag_id == ti.task.gcp_conn_id

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_execute(self, mock_transfer_hook):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_GCS_RAW
        )
        assert mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert not mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_execute_skip_wait(self, mock_transfer_hook):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            wait=False,
            schedule=SCHEDULE_DICT,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_GCS_RAW
        )
        assert not mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert not mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_execute_delete_job_after_completion(self, mock_transfer_hook):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            wait=True,
            delete_job_after_completion=True,
        )

        operator.execute(None)

        mock_transfer_hook.return_value.create_transfer_job.assert_called_once_with(
            body=VALID_TRANSFER_JOB_GCS_RAW
        )
        assert mock_transfer_hook.return_value.wait_for_transfer_job.called
        assert mock_transfer_hook.return_value.delete_transfer_job.called

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_execute_should_throw_ex_when_delete_job_without_wait(self, mock_transfer_hook):
        with pytest.raises(
            AirflowException, match="If 'delete_job_after_completion' is True, then 'wait' must also be True."
        ):
            CloudDataTransferServiceGCSToGCSOperator(
                task_id=TASK_ID,
                source_bucket=GCS_BUCKET_NAME,
                destination_bucket=GCS_BUCKET_NAME,
                description=DESCRIPTION,
                schedule=SCHEDULE_DICT,
                wait=False,
                delete_job_after_completion=True,
            )

    @mock.patch(
        "airflow.providers.google.cloud.operators.cloud_storage_transfer_service.CloudDataTransferServiceHook"
    )
    def test_async_defer_successfully(self, mock_transfer_hook):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        with pytest.raises(TaskDeferred) as exc:
            operator.execute({})
        assert isinstance(exc.value.trigger, CloudStorageTransferServiceCheckJobStatusTrigger)

    def test_async_execute_successfully(self):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        operator.execute_complete(context={}, event={"status": "success"})

    def test_async_execute_error(self):
        operator = CloudDataTransferServiceGCSToGCSOperator(
            task_id=TASK_ID,
            source_bucket=GCS_BUCKET_NAME,
            destination_bucket=GCS_BUCKET_NAME,
            project_id=GCP_PROJECT_ID,
            description=DESCRIPTION,
            schedule=SCHEDULE_DICT,
            deferrable=True,
        )
        with pytest.raises(AirflowException):
            operator.execute_complete(
                context={}, event={"status": "error", "message": "test failure message"}
            )
