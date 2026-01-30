import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def transcribir_audio_fluido(archivo_audio):
    try:
        with open(archivo_audio, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                file=(archivo_audio, audio.read()),
                model="whisper-large-v3",
                response_format="text",
                language="es"
            )
            return transcription
    except Exception as e:
        return f"Error: {str(e)}"

def procesar_pedido_con_ia(pedido, inventario_contexto):
    """Procesa múltiples productos a la vez y sugiere precios del inventario"""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Sos el asistente de Supermercado Morita. 
                    INVENTARIO ACTUAL: {inventario_contexto}.
                    TAREA: El usuario dictará varios productos. Debes extraer: Producto, Cantidad y Precio.
                    Si el producto existe en el inventario, usa ese precio. Si no, estima uno.
                    Responde ÚNICAMENTE con una lista en este formato, un producto por línea:
                    PRODUCTO | CANTIDAD | PRECIO
                    """
                },
                {"role": "user", "content": pedido}
            ],
            temperature=0.1
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"
