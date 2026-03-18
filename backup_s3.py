import os
import boto3
from datetime import datetime

# Configura tus variables
BUCKET_NAME = 'class3boto'
CARPETA_LOCAL = 'respaldo'

# Inicializa el cliente de S3
s3 = boto3.client('s3')

def backup_a_s3():
    fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    carpeta_destino = f'backup_{fecha}/'

    for root, _, files in os.walk(CARPETA_LOCAL):
        for archivo in files:
            ruta_local = os.path.join(root, archivo)
            ruta_relativa = os.path.relpath(ruta_local, CARPETA_LOCAL)
            ruta_s3 = carpeta_destino + ruta_relativa.replace(os.sep, '/')

            print(f'Subiendo {ruta_local} a s3://{BUCKET_NAME}/{ruta_s3}')
            s3.upload_file(ruta_local, BUCKET_NAME, ruta_s3)

    print('Backup completado.')

if __name__ == '__main__':
    backup_a_s3()