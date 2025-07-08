# Spotify API Setup Instructions 🎵

To enable full Spotify integration with your WaterMelon app, you need to register your application with Spotify and get API credentials.

## Step 1: Create Spotify App

1. **Go to Spotify Developer Dashboard**: https://developer.spotify.com/dashboard
2. **Login** with your Spotify account
3. **Click "Create an App"**
4. **Fill in the details**:
   - App name: `WaterMelon Music Player`
   - App description: `Music player integration for WaterMelon website`
   - Website: `http://localhost:5000`
   - Redirect URI: `http://localhost:5000/spotify/callback`
5. **Accept terms** and click "Create"

## Step 2: Get Your Credentials

1. **Click on your newly created app**
2. **Copy the Client ID** (you'll see this immediately)
3. **Click "Show Client Secret"** and copy it
4. **Click "Edit Settings"**
5. **Add Redirect URI**: `http://localhost:5000/spotify/callback`
6. **Save the settings**

## Step 3: Update Your App

Open `app.py` and replace these lines:

```python
SPOTIFY_CLIENT_ID = "your_spotify_client_id_here"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret_here"
```

With your actual credentials:

```python
SPOTIFY_CLIENT_ID = "your_actual_client_id_from_spotify"
SPOTIFY_CLIENT_SECRET = "your_actual_client_secret_from_spotify"
```

## Step 4: Install Required Packages

Run this command to install the requests library:

```bash
pip install requests
```

## Step 5: Test Your Integration

1. **Run your app**: `python app.py`
2. **Login to your WaterMelon dashboard**
3. **Click "Connect Spotify"** in the sidebar
4. **Authorize your app** on Spotify
5. **Start controlling your music directly!**

## What You Can Do After Setup:

✅ **Play Your Playlists**: Click any of your Spotify playlists to start playing
✅ **Control Playback**: Play, pause, next, previous tracks
✅ **Real-time Updates**: See current track info in your sidebar
✅ **Quick Play**: Use "Play My Playlist" button for instant music
✅ **Keyboard Shortcuts**: Ctrl+P for play/pause, Ctrl+M for quick music

## Troubleshooting:

- **"Please connect to Spotify first"**: Make sure you've clicked "Connect Spotify" and authorized the app
- **"Failed to play music"**: Ensure Spotify is open on your device (desktop app or web player)
- **No playlists showing**: Check that your Spotify account has playlists created
- **Connection issues**: Verify your Client ID and Secret are correct

## Security Note:

⚠️ **Important**: Keep your Client Secret private! Don't share it or commit it to public repositories.

For production deployment, use environment variables:

```python
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
```

---

🎉 **Once setup is complete, you'll have full Spotify integration with your WaterMelon app!**
