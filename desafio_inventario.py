import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# ====== CONFIGURACIÓN ======
REGION = "us-east-1"   # cámbiala si tu clase usa otra
SNS_TOPIC_NAME = "alertas-inventario-aws"
METRIC_NAMESPACE = "ClaseAWS/Inventario"
ALARM_NAME = "Alarma-Total-EC2-Alto"
EC2_THRESHOLD = 0  # para prueba rápida: alarmará si hay más de 0 instancias
INVENTORY_FILE = "inventario_aws.json"


def get_clients(region_name: str):
    return {
        "ec2": boto3.client("ec2", region_name=region_name),
        "s3": boto3.client("s3", region_name=region_name),
        "rds": boto3.client("rds", region_name=region_name),
        "lambda": boto3.client("lambda", region_name=region_name),
        "cloudwatch": boto3.client("cloudwatch", region_name=region_name),
        "sns": boto3.client("sns", region_name=region_name),
        "sts": boto3.client("sts", region_name=region_name),
    }


def scan_ec2(ec2_client):
    inventario = []
    paginator = ec2_client.get_paginator("describe_instances")

    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                inventario.append({
                    "instance_id": instance.get("InstanceId"),
                    "state": instance.get("State", {}).get("Name"),
                    "instance_type": instance.get("InstanceType"),
                    "public_ip": instance.get("PublicIpAddress", "-"),
                    "private_ip": instance.get("PrivateIpAddress", "-"),
                })
    return inventario


def scan_s3(s3_client):
    inventario = []
    response = s3_client.list_buckets()
    for bucket in response.get("Buckets", []):
        inventario.append({
            "name": bucket.get("Name"),
            "creation_date": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None,
        })
    return inventario


def scan_rds(rds_client):
    inventario = []
    paginator = rds_client.get_paginator("describe_db_instances")

    for page in paginator.paginate():
        for db in page.get("DBInstances", []):
            inventario.append({
                "db_instance_identifier": db.get("DBInstanceIdentifier"),
                "engine": db.get("Engine"),
                "status": db.get("DBInstanceStatus"),
                "class": db.get("DBInstanceClass"),
                "endpoint": db.get("Endpoint", {}).get("Address", "-"),
            })
    return inventario


def scan_lambda(lambda_client):
    inventario = []
    paginator = lambda_client.get_paginator("list_functions")

    for page in paginator.paginate():
        for fn in page.get("Functions", []):
            inventario.append({
                "function_name": fn.get("FunctionName"),
                "runtime": fn.get("Runtime", "-"),
                "last_modified": fn.get("LastModified"),
                "memory_size": fn.get("MemorySize"),
            })
    return inventario


def generate_inventory(clients):
    account_id = clients["sts"].get_caller_identity()["Account"]

    inventory = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": REGION,
        "account_id": account_id,
        "ec2": scan_ec2(clients["ec2"]),
        "s3": scan_s3(clients["s3"]),
        "rds": scan_rds(clients["rds"]),
        "lambda": scan_lambda(clients["lambda"]),
    }

    inventory["summary"] = {
        "total_ec2": len(inventory["ec2"]),
        "total_s3": len(inventory["s3"]),
        "total_rds": len(inventory["rds"]),
        "total_lambda": len(inventory["lambda"]),
    }

    return inventory


def save_inventory_to_file(inventory, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    print(f"Inventario guardado en: {filename}")


def create_sns_topic(sns_client, topic_name):
    response = sns_client.create_topic(Name=topic_name)
    topic_arn = response["TopicArn"]
    print(f"SNS Topic listo: {topic_arn}")
    return topic_arn


def publish_custom_metrics(cloudwatch_client, summary):
    metric_data = [
        {
            "MetricName": "TotalEC2",
            "Value": summary["total_ec2"],
            "Unit": "Count",
        },
        {
            "MetricName": "TotalS3Buckets",
            "Value": summary["total_s3"],
            "Unit": "Count",
        },
        {
            "MetricName": "TotalRDS",
            "Value": summary["total_rds"],
            "Unit": "Count",
        },
        {
            "MetricName": "TotalLambdaFunctions",
            "Value": summary["total_lambda"],
            "Unit": "Count",
        },
    ]

    cloudwatch_client.put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=metric_data
    )
    print(f"Métricas publicadas en CloudWatch namespace={METRIC_NAMESPACE}")


def create_cloudwatch_alarm(cloudwatch_client, sns_topic_arn):
    cloudwatch_client.put_metric_alarm(
        AlarmName=ALARM_NAME,
        AlarmDescription="Alarma cuando el total de instancias EC2 supera el umbral definido",
        ActionsEnabled=True,
        AlarmActions=[sns_topic_arn],
        MetricName="TotalEC2",
        Namespace=METRIC_NAMESPACE,
        Statistic="Maximum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=EC2_THRESHOLD,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
        Unit="Count",
    )
    print(f"Alarma creada/actualizada: {ALARM_NAME}")


def print_summary(inventory):
    print("\n===== RESUMEN DEL INVENTARIO =====")
    print(f"Cuenta AWS: {inventory['account_id']}")
    print(f"Región: {inventory['region']}")
    print(f"Generado: {inventory['generated_at_utc']}")
    print(f"EC2: {inventory['summary']['total_ec2']}")
    print(f"S3: {inventory['summary']['total_s3']}")
    print(f"RDS: {inventory['summary']['total_rds']}")
    print(f"Lambda: {inventory['summary']['total_lambda']}")


def main():
    try:
        clients = get_clients(REGION)

        inventory = generate_inventory(clients)
        save_inventory_to_file(inventory, INVENTORY_FILE)
        print_summary(inventory)

        sns_topic_arn = create_sns_topic(clients["sns"], SNS_TOPIC_NAME)
        publish_custom_metrics(clients["cloudwatch"], inventory["summary"])
        create_cloudwatch_alarm(clients["cloudwatch"], sns_topic_arn)

        print("\nProceso completado correctamente.")

    except NoCredentialsError:
        print("Error: no se encontraron credenciales de AWS configuradas.")
    except ClientError as e:
        print(f"Error de AWS: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")


if __name__ == "__main__":
    main()
