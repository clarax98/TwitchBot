import logging
import subprocess
import contextlib
import asyncio
import random
import os
import requests
import json 
import re

from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def getTwitchInfo(id):
  url = "https://id.twitch.tv/oauth2/token"
  client_id = '<---CLIENT ID--->'
  client_secret = '<---CLIENT SECRET--->'

  payload = 'client_id='+client_id+'&client_secret='+client_secret+'&grant_type=client_credentials'
  headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
  }

  response = requests.request("POST", url, headers=headers, data=payload)
  data = json.loads(response.text)


  url = "https://api.twitch.tv/helix/videos?id="+str(id)

  payload = {}
  headers = {
    'Authorization': 'Bearer ' + data['access_token'],
    'Client-Id': client_id
  }

  response = requests.request("GET", url, headers=headers, data=payload)

  data = json.loads(response.text)

  return data

def upload_to_youtube(title, output_filename):
    command = [
        'youtube-upload',
        '--title', title,
        '--privacy', 'unlisted',
        output_filename
    ]
    
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        output = result.stdout
        
        # Buscar la URL en la salida utilizando una expresión regular
        url_match = re.search(r'https://www\.youtube\.com/watch\?v=[\w-]+', output)
        if url_match:
            video_url = url_match.group(0)
            return video_url
        else:
            return None
    except subprocess.CalledProcessError as e:
        print("Error al ejecutar el comando:")
        print(e.stderr)
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = await update.message.reply_text("/help si necesitas ayuda")
    message_id = message.message_id
    await context.bot.pin_chat_message(chat_id=update.effective_chat.id, message_id=message_id)

    await update.message.reply_text("Hola, Soy un Bot de uso personal desarollado por Clara")
    await update.message.reply_text("Mi funcion principal es...")
    await update.message.reply_text("Descargar videos de Twitch y resubirlos en oculto a youtube o a plex, o por telegram")
    await update.message.reply_text("A continuacion describire los comandos:")
    await update.message.reply_text("/modo : Cambiar entre subir a youtube, plex o telegram (Youtube y plex solo disponible para Admins)")
    await update.message.reply_text("/calidad : Cambiar la calidad de descarga")
    await update.message.reply_text("Por defecto la calidad es 720p y el metodo de descarga es telegram")
    await update.message.reply_text("Si da algun error prueba con otra calidad, esto es una beta")
    await update.message.reply_text("Utilizamos file.io debido a las limitaciones de telegram")
    await update.message.reply_text("/help para volver aqui")
    await update.message.reply_text("Simplemente enviame el enlace del video o clip que te interesa")

async def modo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Plex", callback_data="upload_plex"),
         InlineKeyboardButton("Youtube", callback_data="upload_youtube"),
         InlineKeyboardButton("Telegram", callback_data="upload_telegram"),
        ]
    ])
    await update.message.reply_text("Elije el modo", reply_markup=reply_markup)



async def upload_to_youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['upload_service'] = 'youtube'
    await update.message.reply_text("Ahora el video se subirá a YouTube.")



async def upload_to_plex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['upload_service'] = 'plex'
    await update.message.reply_text("Ahora el video se subirá a Plex.")


# Función para manejar los callback
async def handle_callback(update, context):
    query = update.callback_query
    callback_data = query.data
    
    if callback_data == "upload_youtube":
        if update.effective_chat.id == 6067448436:
            context.user_data['upload_service'] = 'youtube'
            await query.message.reply_text("Ahora el video se subirá a YouTube.")
        else:
            await query.message.reply_text("Opcion limitada algunos usuarios")

    elif callback_data == "upload_plex":
        if update.effective_chat.id == 6067448436:
            context.user_data['upload_service'] = 'plex'
            await query.message.reply_text("Ahora el video se subirá a Plex.")
        else:
            await query.message.reply_text("Opcion limitada algunos usuarios")
    
    elif callback_data == "upload_telegram":
        context.user_data['upload_service'] = 'telegram'
        await query.message.reply_text("Ahora el video se subirá a Telegram.")

    elif callback_data in ["1080p60", "720p60", "1080p", "720p", "480p", "360p", "160p", "audio_only"] :
        context.user_data['quality'] = callback_data
        await query.message.reply_text("Ahora la calidad de descarga es: " + callback_data)


async def calidad_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = InlineKeyboardMarkup([
        [
         InlineKeyboardButton("1080p60", callback_data="1080p60"),
         InlineKeyboardButton("720p60", callback_data="720p60"),
         InlineKeyboardButton("1080p", callback_data="1080p"),],[
         InlineKeyboardButton("720p", callback_data="720p"),
         InlineKeyboardButton("480p", callback_data="480p"),
         InlineKeyboardButton("360p", callback_data="360p"),],[
         InlineKeyboardButton("160p", callback_data="160p"),
         InlineKeyboardButton("audio_only", callback_data="audio_only"),]
        
    ])
    await update.message.reply_text("Elije la calidad de descarga", reply_markup=reply_markup)



async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""

    upload_service = context.user_data.get('upload_service', 'telegram')  # Valor predeterminado es YouTube
    quality = context.user_data.get('quality', '720p')  # Valor predeterminado es 720p60


    a = update.message.text
    twitch_url_pattern = r'https://(www\.)?(twitch\.tv/videos/|clips\.twitch\.tv/)[^\s/$.?#].[^\s]*'
    match = re.search(twitch_url_pattern, a)
    if not match:
        await update.message.reply_text("No es una URL valida de Twitch")
    else:
        await update.message.reply_text("Procesando... Esto puede tardar...")
        rand = random.randint(10000, 999999)
        output_filename = str(rand)+'.mp4'
        subprocess.call(['twitch-dl', 'download', '-q', quality, '--overwrite', '-o', output_filename, update.message.text])

        
        try:

            if upload_service == 'youtube':
                video_id = a.replace('https://www.twitch.tv/videos/', '')
                title = getTwitchInfo(video_id)['data'][0]['title']
                output = upload_to_youtube(title, output_filename)
                if output is not None:
                    print("Salida:", output)
                    await update.message.reply_text("Video subido a Youtube " +  output)
                else:
                    await update.message.reply_text("Video subido a Youtube")

            elif upload_service == 'plex':
                # Mover el archivo a la carpeta 'video'
                destination_path = '/home/clara/video/' + output_filename
                os.rename(output_filename, destination_path)
                await update.message.reply_text("Video subido a Plex. " )
            
            elif upload_service == 'telegram':
                video_path = '/home/clara/' + output_filename
                # Envia el video al chat
                
                response = requests.post("https://file.io", files={'file': open(video_path, 'rb')})
                response_data = response.json()
                
                os.remove(video_path)  # Eliminar el archivo local después de subirlo
                
                if response_data.get('success'):
                    download_link = response_data.get('link')
                    await update.message.reply_text(f"Aquí tienes tu enlace de descarga temporal: {download_link}")
                else:
                    await update.message.reply_text("No se pudo generar el enlace de descarga temporal.")

        except Exception as e:
            print(e)
            print("Tipo de error:", type(e))  # Imprime el tipo de excepción
            await update.message.reply_text("Ocurrió un error al subir el video. " + str(e))



async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    await update.message.reply_text("Hola, Soy un Bot de uso personal desarollado por Clara")
    await update.message.reply_text("Mi funcion principal es...")
    await update.message.reply_text("Descargar videos de Twitch y resubirlos en oculto a youtube o a plex, o por telegram")
    await update.message.reply_text("A continuacion describire los comandos:")
    await update.message.reply_text("/modo : Cambiar entre subir a youtube, plex o telegram (Youtube y plex solo disponible para Admins)")
    await update.message.reply_text("/calidad : Cambiar la calidad de descarga")
    await update.message.reply_text("Por defecto la calidad es 720p y el metodo de descarga es telegram")
    await update.message.reply_text("Si da algun error prueba con otra calidad, esto es una beta")
    await update.message.reply_text("Utilizamos file.io debido a las limitaciones de telegram")
    await update.message.reply_text("/help para volver aqui")
    await update.message.reply_text("Simplemente enviame el enlace del video o clip que te interesa")
    

if __name__ == '__main__':
    application = ApplicationBuilder().token('<---BOT-TOKEN--->').read_timeout(3000).write_timeout(3000).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_handler(start_handler)
    

    youtube_handler = CommandHandler('youtube', upload_to_youtube_command)
    application.add_handler(youtube_handler)
        

    plex_handler = CommandHandler('plex', upload_to_plex_command)
    application.add_handler(plex_handler)


    modo_handler = CommandHandler('modo', modo_command)
    application.add_handler(modo_handler)

    calidad_handler = CommandHandler('calidad', calidad_handler)
    application.add_handler(calidad_handler)

    help_handler = CommandHandler('help', help_handler)
    application.add_handler(help_handler)
    
    # Agregar un manejador para los eventos de callback
    callback_handler = CallbackQueryHandler(handle_callback)
    application.add_handler(callback_handler)


    application.run_polling()
