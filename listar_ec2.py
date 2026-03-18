import boto3

def listar_instancias_ec2():
    ec2 = boto3.client('ec2')
    respuesta = ec2.describe_instances()
    print(f"{'Instance ID':<20} {'Estado':<15} {'Tipo':<15} {'IP Pública':<20}")
    print('-' * 70)
    for reserva in respuesta['Reservations']:
        for instancia in reserva['Instances']:
            instance_id = instancia.get('InstanceId', '-')
            estado = instancia.get('State', {}).get('Name', '-')
            tipo = instancia.get('InstanceType', '-')
            ip_publica = instancia.get('PublicIpAddress', '-')
            print(f"{instance_id:<20} {estado:<15} {tipo:<15} {ip_publica:<20}")

if __name__ == '__main__':
    listar_instancias_ec2()
