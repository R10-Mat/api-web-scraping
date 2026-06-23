import requests
import boto3
import uuid

def lambda_handler(event, context):
    url = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/2026"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {
                'statusCode': response.status_code,
                'body': f'Error al acceder a los datos del IGP: {response.text}'
            }
        
        todos_los_sismos = response.json()
        
        sismos = todos_los_sismos[:10]

    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error al conectar o parsear la API: {str(e)}'
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TablaWebScrappingIGP')

    try:
        scan = table.scan()
        with table.batch_writer() as batch:
            for each in scan.get('Items', []):
                batch.delete_item(Key={'id': each['id']})
    except Exception as e:
        print(f"Aviso: No se pudo limpiar la tabla: {str(e)}")

    rows_processed = []
    for i, sismo in enumerate(sismos, start=1):
        item = {
            'id': str(uuid.uuid4()),
            '#': i,
            'Cod_reporte': sismo.get('cod_reporte', 'N/A'),
            'Referencia': sismo.get('referencia', 'N/A'),
            'Magnitud': str(sismo.get('magnitud', '0.0')),
            'Fecha_Hora': f"{sismo.get('fecha_utc', '')} {sismo.get('hora_utc', '')}".strip()
        }
        table.put_item(Item=item)
        rows_processed.append(item)

    return {
        'statusCode': 200,
        'body': rows_processed
    }
