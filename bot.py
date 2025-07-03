import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()
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

# Inicia el bot con el token y un manejo de errores global para mayor estabilidad
try:
    client.run(DISCORD_TOKEN)
except Exception as e:
    print(f"Error CRÍTICO al ejecutar el bot: {e}")
