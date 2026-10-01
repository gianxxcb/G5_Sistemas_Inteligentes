import os
from google import genai
from google.genai import types

class AgenteCoordinador:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") 
        self.client = genai.Client(api_key=api_key) 

    def redactar_respuesta_docente(self, solicitud: dict, dictamen: dict) -> str:
        prompt = f"""
        Actúa como una persona real del equipo de coordinación académica (no un robot ni un sistema automatizado). 
        Redacta un correo electrónico de respuesta cotidiano, sumamente natural, cordial, empático y directo 
        dirigido al docente que solicitó el aula.

        Detalles de la solicitud del docente:
        - Materia: {solicitud.get('materia')}
        - Aforo: {solicitud.get('aforo')}
        - Laboratorio requerido: {solicitud.get('requiere_laboratorio')}
        - Horario: {solicitud.get('horario_inicio')} a {solicitud.get('horario_fin')}

        Resultado del sistema:
        - ¿Aprobado?: {dictamen.get('aprobado')}
        - Aula asignada: {dictamen.get('aula_asignada')}
        - ¿Se requirió reubicación por cercanía/disponibilidad?: {dictamen.get('requiere_alternativa')}
        - Aula alternativa asignada: {dictamen.get('aula_alternativa')}
        - Motivo / Observaciones: {dictamen.get('motivo')}

        Instrucciones de estilo:
        1. Saluda al docente por su nombre de forma amable (puedes usar un saludo genérico respetuoso como "Estimado/a docente").
        2. Explícale de manera muy sencilla y humana qué aula se le asignó y por qué (si hubo que cambiarla de salón, explícaselo de forma conversacional y comprensible, como si tú misma/o hubieras revisado el espacio).
        3. Evita tecnicismos de programación, palabras como "dictamen técnico", "algoritmo A*" o "hechos normalizados". Habla como un ser humano de la facultad.
        4. Despídete cordialmente deseándole el mayor de los éxitos en su clase.
        5. Devuelve únicamente el cuerpo del mensaje listo para enviar.
        """

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            return f"Hola, te escribo para confirmarte que tu reserva para la materia {solicitud.get('materia')} ha sido procesada con éxito. Se te ha asignado el aula {dictamen.get('aula_asignada')}. ¡Saludos!"