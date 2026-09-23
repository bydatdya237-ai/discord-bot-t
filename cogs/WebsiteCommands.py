import os
import json
import discord
from discord.ext import commands
from flask import Flask, jsonify


# =========================================================
# إعدادات الموقع
# =========================================================

WEBSITE_API_KEY = os.getenv("WEBSITE_API_KEY", "")

app = Flask("website_commands")


# =========================================================
# استخراج معلومات الأوامر
# =========================================================

def get_commands_data(bot):

    commands_list = []

    for command in bot.commands:

        # تجاهل الأوامر المخفية
        if command.hidden:
            continue

        # تجاهل الأوامر التابعة لـ Group
        if command.parent is not None:
            continue

        commands_list.append({
            "name": command.name,
            "description": command.help or command.description or "لا يوجد وصف لهذا الأمر.",
            "aliases": list(command.aliases),
        })

    commands_list.sort(
        key=lambda x: x["name"].lower()
    )

    return commands_list


# =========================================================
# API الأوامر
# =========================================================

@app.route("/api/commands")
def commands_api():

    # التحقق من المفتاح إذا تم وضعه
    if WEBSITE_API_KEY:

        from flask import request

        api_key = request.headers.get("X-Website-Key")

        if api_key != WEBSITE_API_KEY:
            return jsonify({
                "success": False,
                "error": "Unauthorized"
            }), 401

    bot = website_bot

    return jsonify({
        "success": True,
        "count": len(get_commands_data(bot)),
        "commands": get_commands_data(bot)
    })


# =========================================================
# حالة الموقع
# =========================================================

@app.route("/api/status")
def status_api():

    bot = website_bot

    return jsonify({
        "success": True,
        "bot_ready": bot.is_ready(),
        "bot_name": str(bot.user) if bot.user else None,
        "commands_count": len(get_commands_data(bot))
    })


# =========================================================
# تشغيل API
# =========================================================

website_bot = None


def run_website_api():

    port = int(
        os.getenv("WEBSITE_API_PORT", "8081")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# Cog
# =========================================================

class WebsiteCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        global website_bot
        website_bot = bot

        print(
            "🌐 WebsiteCommands تم تحميله"
        )

        print(
            f"📋 عدد الأوامر الحالية: "
            f"{len(bot.commands)}"
        )


async def setup(bot):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ WebsiteCommands جاهز"
    )
