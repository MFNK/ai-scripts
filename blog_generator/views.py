from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.conf import settings
import os
import assemblyai as aai
from openai import OpenAI
from pytubefix import YouTube # This is solution
import requests
import google.generativeai as genai
from .models import Scripts

# Create your views here.
@login_required
def index(request):
    return render(request, "index.html")

@csrf_exempt #dont require csrf
def generate_blog(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body) #gets body from index.html in dictionary form
            yt_link = data['link'] # gets the link from data
        except (KeyError, json.JSONDecodeError): #problem with the json value
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        
        # Get yt title
        title = yt_title(yt_link)
        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)


        # use openai to generate blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        #save blog article to database
        new_script = Scripts.objects.create(
            user = request.user,
            youtube_title = title,
            youtube_link = yt_link,
            generated_content = blog_content,
        )
        new_script.save() #saves article to db


        # return blog article as a response


        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def yt_title(link):
    try:
        yt = YouTube(link)
        return yt.title
    except Exception as e:
        print(f"Error fetching title: {e}")
        return "Unknown Title"


def download_audio(link):
    try:
        yt = YouTube(link, use_po_token=True)
        video = yt.streams.filter(only_audio=True).first()
        if not video:
            print("No audio stream found")
            return None

        out_file = video.download(output_path=settings.MEDIA_ROOT)
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        os.rename(out_file, new_file)
        return new_file
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None


def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    print(aai.settings.api_key)

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text

def generate_blog_from_transcription(transcription):
    try:
        prompt = f"Summarize this transcript into an interesting to read script for a tiktok. Please dont include any symbols just a readable paragraph:\n\n{transcription}\n\nScript:"

        model = genai.GenerativeModel("gemini-2.0-flash")  # Ensure correct model name
        response = model.generate_content(prompt)

        return response.text.strip()  # ✅ Return plain text, not a JsonResponse
    except Exception as e:
        print(f"Error generating blog: {e}")
        return None

    
def script_list(request):
    script_items = Scripts.objects.filter(user=request.user)
    return render(request, "all-scripts.html", {'script_items': script_items})

def script_details(request, pk):
    script_item_detail = Scripts.objects.get(id=pk)
    if request.user == script_item_detail.user:
        return render(request, 'script-details.html', {'script_item_detail': script_item_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None: #if user is not blank
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message })

    return render(request, "login.html")


def user_signup(request):
    if request.method == 'POST': #If user clicked signup button
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = "Error creating account"
                return render(request, "signup.html", {'error_message': error_message})
        else:
            error_message = "Passwords do not match. Please try again."
            return render(request, "signup.html", {'error_message': error_message})
    return render(request, "signup.html")


def user_logout(request):
    logout(request)
    return redirect('/')

