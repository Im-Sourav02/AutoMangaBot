# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


from aiohttp import web

async def web_server():
    async def handle(request):
        return web.Response(text="bot is running!")

    async def autobatch_webview(request):
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>
    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        // Immediately close and send data back to bot
        tg.sendData("autobatch_trigger");
        tg.close();
    </script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/webview/autobatch", autobatch_webview)
    return app


# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat