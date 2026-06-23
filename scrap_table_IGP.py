import requests
import boto3
import uuid
import re

def lambda_handler(event, context):
    # URL de la página principal donde está escondida la API Key
    main_url = "https://ultimosismo.igp.gob.pe/productos/reportes-sismicos"
    graphql_url = "https://vgsq5e345rbslkzskqx6efewsu.appsync-api.us-east-1.amazonaws.com/graphql"

    # 1. Conectarse a la página principal para robar la API Key actual
    try:
        html_response = requests.get(main_url, timeout=10)
        if html_response.status_code != 200:
            return {
                'statusCode': html_response.status_code,
                'body': 'No se pudo acceder a la página principal del IGP para obtener la clave.'
            }
        
        # Usamos Expresiones Regulares (regex) para buscar el patrón graphQLApiKey:"..." en el HTML
        match = re.search(r'graphQLApiKey\s*:\s*"([^"]+)"', html_response.text)
        if not match:
            return {
                'statusCode': 500,
                'body': 'No se encontró la etiqueta graphQLApiKey en el código fuente de la página.'
            }
        
        # Esta es la API Key fresquita extraída en tiempo real
        api_key = match.group(1)

    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error al intentar extraer la clave dinámica: {str(e)}'
        }

    # 2. Configurar la consulta para traer exactamente los 10 primeros sismos
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
        "x-api-key": api_key  # Usamos la clave que acabamos de extraer
    }

    # 3. Realizar la petición POST a la API de GraphQL
    try:
        response = requests.post(graphql_url, json={'query': query}, headers=headers, timeout=10)
        if response.status_code != 200:
            return {
                'statusCode': response.status_code,
                'body': f'Error en la API del IGP: {response.text}'
            }
        
        data = response.json()
        
        if "errors" in data:
            return {
                'statusCode': 401,
                'body': f'La API rechazó la clave extraída. Errores: {data["errors"]}'
            }
            
        sismos = data.get("data", {}).get("listUltimoSismos", {}).get("items", [])
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error al procesar los datos de la API: {str(e)}'
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
        print(f"Aviso: No se pudo limpiar la tabla: {str(e)}")

    # 6. Insertar los 10 nuevos registros
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

    # 7. Retornar los datos limpios a Postman
    return {
        'statusCode': 200,
        'body': rows_processed
    }
