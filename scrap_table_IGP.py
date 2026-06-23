import requests
import boto3
import uuid

def lambda_handler(event, context):
    # 1. Endpoint y credenciales públicas del IGP (sacadas de su AppSync oficial)
    graphql_url = "https://vgsq5e345rbslkzskqx6efewsu.appsync-api.us-east-1.amazonaws.com/graphql"
    api_key = "da2-dauvp6fdtngv3p55rt7buu6r2e"

    # 2. Consulta GraphQL configurada exactamente para traer los 10 primeros registros
    query = """
    query ObtenerDiezSismos {
      listUltimoSismos(limit: 10, sortDirection: DESC) {
        items {
          cod_reporte
          referencia
          magnitud
          fecha_utc
          hora_utc
        }
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    # 3. Realizar la petición POST
    try:
        response = requests.post(graphql_url, json={'query': query}, headers=headers)
        if response.status_code != 200:
            return {
                'statusCode': response.status_code,
                'body': f'Error al conectarse a la API del IGP: {response.text}'
            }
        
        data = response.json()
        sismos = data.get("data", {}).get("listUltimoSismos", {}).get("items", [])
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error en la petición: {str(e)}'
        }

    # 4. Conectarse a DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TablaWebScrappingIGP')

    # 5. Limpiar los elementos anteriores de la tabla
    try:
        scan = table.scan()
        with table.batch_writer() as batch:
            for each in scan.get('Items', []):
                batch.delete_item(Key={'id': each['id']})
    except Exception as e:
        print(f"Aviso: No se pudo limpiar la tabla o estaba vacía: {str(e)}")

    # 6. Insertar los 10 nuevos registros
    rows_processed = []
    for i, sismo in enumerate(sismos, start=1):
        item = {
            'id': str(uuid.uuid4()),                  # ID único requerido por tu tabla
            '#': i,                                   # Número correlativo (1 al 10)
            'Cod_reporte': sismo.get('cod_reporte', 'N/A'),
            'Referencia': sismo.get('referencia', 'N/A'),
            'Magnitud': str(sismo.get('magnitud', '0.0')),
            'Fecha_Hora': f"{sismo.get('fecha_utc', '')} {sismo.get('hora_utc', '')}".strip()
        }
        table.put_item(Item=item)
        rows_processed.append(item)

    # 7. Retornar el resultado exitoso
    return {
        'statusCode': 200,
        'body': rows_processed
    }
