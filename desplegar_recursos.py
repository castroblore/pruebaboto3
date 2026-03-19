import boto3
import time
from botocore.exceptions import ClientError, NoCredentialsError

REGION = "us-east-1"
BUCKET_NAME = "clasebotos32026-inventario"
INSTANCE_NAME = "ec2-inventario-prueba"
INSTANCE_TYPE = "t2.micro"

def crear_bucket_s3(s3_client):
    try:
        if REGION == "us-east-1":
            s3_client.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3_client.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": REGION}
            )
        print(f"Bucket creado: {BUCKET_NAME}")
    except ClientError as e:
        codigo = e.response["Error"]["Code"]
        if codigo in ["BucketAlreadyOwnedByYou", "BucketAlreadyExists"]:
            print(f"El bucket ya existe: {BUCKET_NAME}")
        else:
            raise

def obtener_ami_amazon_linux(ssm_client):
    response = ssm_client.get_parameter(
        Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    )
    return response["Parameter"]["Value"]

def lanzar_ec2(ec2_resource, ec2_client, ami_id):
    response = ec2_resource.create_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": INSTANCE_NAME}]
            }
        ]
    )

    instancia = response[0]
    print(f"Instancia lanzada: {instancia.id}")
    print("Esperando a que la instancia esté en running...")
    instancia.wait_until_running()

    # refrescar atributos
    instancia.reload()

    print("Instancia en ejecución:")
    print(f"  Instance ID: {instancia.id}")
    print(f"  Estado: {instancia.state['Name']}")
    print(f"  Tipo: {instancia.instance_type}")
    print(f"  IP pública: {instancia.public_ip_address}")

def main():
    try:
        session = boto3.Session(region_name=REGION)

        s3_client = session.client("s3")
        ssm_client = session.client("ssm")
        ec2_client = session.client("ec2")
        ec2_resource = session.resource("ec2")

        print("Creando bucket S3...")
        crear_bucket_s3(s3_client)

        print("Consultando AMI más reciente de Amazon Linux...")
        ami_id = obtener_ami_amazon_linux(ssm_client)
        print(f"AMI encontrada: {ami_id}")

        print("Lanzando instancia EC2...")
        lanzar_ec2(ec2_resource, ec2_client, ami_id)

        print("\nRecursos desplegados correctamente.")

    except NoCredentialsError:
        print("Error: no se encontraron credenciales de AWS.")
    except ClientError as e:
        print(f"Error de AWS: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()