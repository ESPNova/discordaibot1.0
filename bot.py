import discord
import os
import google.generativeai as genai
import json
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# --- Verificación de Secretos Críticos ---
import sys

print("Iniciando verificación de secretos...")
required_secrets = ["DISCORD_TOKEN", "GOOGLE_API_KEY", "GUILD_ID", "ADMIN_CHANNEL_ID"]
missing_secrets = [secret for secret in required_secrets if not os.getenv(secret)]

if missing_secrets:
    print("="*50)
    print("ERROR CRÍTICO: FALTAN VARIABLES DE ENTORNO (SECRETS)")
    print("El bot no puede arrancar porque no se encontraron los siguientes secretos:")
    for secret in missing_secrets:
        print(f"  - {secret}")
    print("\nPor favor, ve a la sección 'Secrets' en Replit y asegúrate de que:")
    print("1. Todos los secretos de la lista de arriba existen.")
    print("2. Los nombres (Keys) están escritos EXACTAMENTE como aparecen aquí.")
    print("3. Ningún valor (Value) está vacío.")
    print("="*50)
    sys.exit(1) # Detiene el programa con un error claro

print("✅ Todos los secretos críticos han sido cargados correctamente.")
# --- Fin de la Verificación ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configura la clave de la API de Google
genai.configure(api_key=GOOGLE_API_KEY)

# Define los "intents" del bot. Son necesarios para que el bot pueda recibir ciertos eventos de Discord.
intents = discord.Intents.default()
intents.message_content = True  # Necesario para leer el contenido de los mensajes

# Crea una instancia del cliente de Discord
client = discord.Client(intents=intents)
# Crea un árbol de comandos para registrar los comandos de barra (/)
tree = discord.app_commands.CommandTree(client)

# Diccionario para almacenar los historiales de conversación por usuario
# La clave será el ID de usuario, y el valor será el historial de chat de Gemini
conversation_histories = {}

# Evento que se ejecuta cuando el bot se ha conectado correctamente a Discord
@client.event
async def on_ready():
    print(f'¡Bot conectado como {client.user}!')
    # Sincroniza los comandos de barra con Discord. 
    # Esto puede tardar un poco la primera vez.
    await tree.sync()
    print("Comandos sincronizados.")

# Define el comando de barra /ia
@tree.command(name="ia", description="Habla con la IA (con memoria)")
async def ia_command(interaction: discord.Interaction, mensaje: str):
    try:
        await interaction.response.defer()
        user_id = interaction.user.id

        # Obtiene el historial de conversación para el usuario o crea uno nuevo
        # El historial se guarda en el formato que espera la API de Gemini
        user_history = conversation_histories.get(user_id, [])

        # Inicia el modelo y la sesión de chat con el historial existente
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        chat = model.start_chat(history=user_history)

        # Envía el nuevo mensaje de forma asíncrona
        response = await chat.send_message_async(mensaje)
        ai_message = response.text

        # Actualiza el historial en nuestra variable global para el próximo mensaje
        # El objeto 'chat.history' contiene la conversación completa y actualizada
        conversation_histories[user_id] = chat.history

        # Envía la respuesta
        await interaction.followup.send(f'**Tu pregunta:** {mensaje}\n**Respuesta de la IA:** {ai_message}')

    except Exception as e:
        print(f"Error en el comando /ia: {e}")
        await interaction.followup.send("Lo siento, ha ocurrido un error al procesar tu solicitud.")

# Define el comando de barra /reset_ia
@tree.command(name="reset_ia", description="Borra tu historial de conversación con la IA")
async def reset_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in conversation_histories:
        del conversation_histories[user_id]
        await interaction.response.send_message("¡Tu historial de conversación ha sido borrado!", ephemeral=True)
    else:
        await interaction.response.send_message("No tienes ningún historial de conversación para borrar.", ephemeral=True)

# --- Keep-alive web server para Replit ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está en línea y funcionando."

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -----------------------------------------

# --- Sistema de Seguridad por IA ---
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
SERVER_RULES = ""
try:
    with open('rules.txt', 'r', encoding='utf-8') as f:
        SERVER_RULES = f.read()
except FileNotFoundError:
    print("ADVERTENCIA: El archivo rules.txt no se encontró. El sistema de seguridad no funcionará sin él.")
    SERVER_RULES = "No se han definido reglas."

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return

    if message.content.startswith('/'):
        return

    if not ADMIN_CHANNEL_ID or not SERVER_RULES or SERVER_RULES == "No se han definido reglas.":
        return

    try:
        security_prompt = (
            "Eres un moderador de Discord de IA llamado 'SecurityGuard'. Tu única tarea es analizar un mensaje de un usuario y determinar si infringe las reglas del servidor. Debes ser muy preciso y evitar falsos positivos.\n\n"
            f"--- REGLAS DEL SERVIDOR ---\n{SERVER_RULES}\n--------------------------\n\n"
            f"--- MENSAJE A ANALIZAR ---\nUsuario: {message.author.display_name}\nMensaje: \"{message.content}\"\n--------------------------\n\n"
            "--- ANÁLISIS ---\n"
            "1. ¿El mensaje infringe alguna de las reglas del servidor basándote en su contenido y contexto? Responde solo 'Sí' o 'No'.\n"
            "2. Si la respuesta es 'Sí', ¿qué regla específica se ha infringido? Cita el número y el texto de la regla.\n"
            "3. Si la respuesta es 'Sí', ¿cuál es tu recomendación de penalización? Elige una de estas opciones: [Warn, Mute (1 hora), Kick, Ban].\n"
            "4. Si la respuesta es 'Sí', proporciona una breve justificación (1-2 frases) de por qué crees que se ha infringido la regla.\n\n"
            "--- FORMATO DE RESPUESTA ---\n"
            "Proporciona tu respuesta en un formato JSON estricto. Si no hay infracción, el valor de 'infraccion' debe ser 'No'. Ejemplo:\n"
            '{\n' \
            '  "infraccion": "Sí",\n' \
            '  "regla_infringida": "Regla 2: No hacer spam.",\n' \
            '  "penalizacion_recomendada": "Mute (1 hora)",\n' \
            '  "justificacion": "El usuario ha enviado el mismo mensaje varias veces seguidas."\n' \
            '}'
        )

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = await model.generate_content_async(security_prompt)
        
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        analysis = json.loads(cleaned_response)

        if analysis.get("infraccion") == "Sí":
            admin_channel = client.get_channel(int(ADMIN_CHANNEL_ID))
            if admin_channel:
                embed = discord.Embed(
                    title="⚠️ Alerta de Seguridad: Posible Infracción de Reglas",
                    color=discord.Color.red()
                )
                embed.add_field(name="👤 Usuario", value=message.author.mention, inline=False)
                embed.add_field(name="📜 Regla Infringida", value=analysis.get("regla_infringida", "No especificada"), inline=False)
                embed.add_field(name="💬 Mensaje Original", value=f"```{message.content}```", inline=False)
                embed.add_field(name="⚖️ Penalización Recomendada", value=analysis.get("penalizacion_recomendada", "No especificada"), inline=False)
                embed.add_field(name="🧠 Justificación de la IA", value=analysis.get("justificacion", "No especificada"), inline=False)
                embed.add_field(name="🔗 Enlace al Mensaje", value=f"[Ir al mensaje]({message.jump_url})", inline=False)
                embed.set_footer(text="Este es un análisis automático por IA. Por favor, verifique antes de actuar.")
                
                await admin_channel.send(embed=embed)

    except Exception as e:
        print(f"Error en el sistema de seguridad on_message: {e}")

# Inicia el bot con el token y un manejo de errores global para mayor estabilidad
try:
    keep_alive()
    client.run(DISCORD_TOKEN)
except Exception as e:
    print(f"Error CRÍTICO al ejecutar el bot: {e}")
