import discord
from discord import app_commands
from discord.ext import commands
import json, os, asyncio
from datetime import datetime
from filters import banned_words, caps_limit
from utils import log_action, warn_user, get_warns, clear_warns, apply_punishment

# ==========================
#         НАСТРОЙКИ
# ==========================
GUILD_ID = 1427588125126819913
LOG_CHANNEL_ID = 1427600162615726111
ROLE_UNVERIFIED = 1427612004352393336
ROLE_VERIFIED = 1427612455575617636
ROLE_MUTED = 1427654016728568050
MOD_ROLES = [
    1427595363736490024,
    1427595483316092979,
    1427595591189397544,
    1427595715428880436
]

# ==========================
#         ТОКЕН
# ==========================
import os
TOKEN = os.getenv("TOKEN")

# ==========================
#         ИНТЕНТЫ
# ==========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
#         ПАПКА DATA
# ==========================
if not os.path.exists("data"):
    os.makedirs("data")

WARN_FILE = "data/warns.json"
if not os.path.exists(WARN_FILE):
    with open(WARN_FILE, "w") as f:
        json.dump({}, f)

# ==========================
#         КЭШ
# ==========================
user_message_cache = {}


# ==========================
#         ОНЛАЙН И СТАТУС
# ==========================
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ {bot.user} подключён!")

    # --- установка активности
    activity = discord.Game(name="Advanced Moderation", type=discord.ActivityType.playing)
    await bot.change_presence(status=discord.Status.idle, activity=activity)

    await log_action(bot, LOG_CHANNEL_ID, "🟢 **DYNAM Automod активен!**")


# ==========================
#         СОБЫТИЕ on_message
# ==========================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    lowered = message.content.lower()
    author_id = str(message.author.id)
    now = asyncio.get_event_loop().time()

    # --- антиспам
    if author_id not in user_message_cache:
        user_message_cache[author_id] = []
    user_message_cache[author_id].append(now)
    user_message_cache[author_id] = [t for t in user_message_cache[author_id] if now - t < 5]
    if len(user_message_cache[author_id]) > 6:
        await message.delete()
        await warn_user(bot, message.author, "Флуд (п.1.2)", LOG_CHANNEL_ID)
        return

    # --- антикапс
    if sum(1 for c in message.content if c.isupper()) > caps_limit and len(message.content) > 10:
        await message.delete()
        await warn_user(bot, message.author, "Злоупотребление CAPS LOCK (п.1.2)", LOG_CHANNEL_ID)
        return

    # --- фильтр слов
    if any(word in lowered for word in banned_words):
        await message.delete()
        await warn_user(bot, message.author, "Оскорбления/мат (п.1.2)", LOG_CHANNEL_ID)
        return

    # --- ссылки, реклама, залго, упоминания
    urls = ["http://", "https://", "www.", "discord.gg", "t.me", "vk.com", "boosty", "promo"]
    if any(url in lowered for url in urls) or len(message.mentions) >= 1:
        await message.delete()
        mod_ping = " ".join([f"<@&{r}>" for r in MOD_ROLES])
        embed = discord.Embed(description=f"{message.author.mention} нарушил правило 4.1/4.2\n"
                                          f"Просьба выдать ему наказание!\n💬 Сообщение: {message.content}\n{mod_ping}",
                              color=0xFF0000)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)
        return

    await bot.process_commands(message)


# ==========================
#         SLASH-КОМАНДЫ
# ==========================
# --- /warn
@bot.tree.command(
    name="warn",
    description="Выдать предупреждение пользователю с указанием причины",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь", reason="Причина предупреждения")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    await warn_user(bot, user, reason, LOG_CHANNEL_ID)
    await interaction.response.send_message(f"⚠️ {user.mention} получил варн по причине: {reason}", ephemeral=True)


# --- /warnlist
@bot.tree.command(
    name="warnlist",
    description="Показать количество предупреждений у пользователя",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь")
async def warnlist(interaction: discord.Interaction, user: discord.Member):
    count = get_warns(user.id)
    await interaction.response.send_message(f"📋 У {user.mention} {count} предупреждений", ephemeral=True)


# --- /clearwarns
@bot.tree.command(
    name="clearwarns",
    description="Очистить все предупреждения пользователя (только для админов)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь")
async def clearwarns_cmd(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Только администратор", ephemeral=True)
    clear_warns(user.id)
    await log_action(bot, LOG_CHANNEL_ID, f"🧹 {interaction.user} очистил предупреждения {user}")
    await interaction.response.send_message(f"✅ Предупреждения {user.mention} очищены", ephemeral=True)


# --- /mute
@bot.tree.command(
    name="mute",
    description="Замутить пользователя на указанное время с причиной",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь", time="Время (например: 30m, 2h)", reason="Причина")
async def mute(interaction: discord.Interaction, user: discord.Member, time: str, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    role_muted = interaction.guild.get_role(ROLE_MUTED)
    await user.add_roles(role_muted)
    await log_action(bot, LOG_CHANNEL_ID, f"🔇 {user} замучен на {time}. Причина: {reason}")
    await interaction.response.send_message(f"🔇 {user.mention} замучен на {time}", ephemeral=True)

    # Парсинг времени
    sec = 0
    if time.endswith("m"):
        sec = int(time[:-1]) * 60
    elif time.endswith("h"):
        sec = int(time[:-1]) * 3600
    elif time.endswith("d"):
        sec = int(time[:-1]) * 86400
    if sec > 0:
        await asyncio.sleep(sec)
        await user.remove_roles(role_muted)
        await log_action(bot, LOG_CHANNEL_ID, f"✅ {user} размучен автоматически после {time}")


# --- /unmute
@bot.tree.command(
    name="unmute",
    description="Снять мут с пользователя",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    role_muted = interaction.guild.get_role(ROLE_MUTED)
    await user.remove_roles(role_muted)
    await log_action(bot, LOG_CHANNEL_ID, f"🔊 {user} размучен вручную")
    await interaction.response.send_message(f"🔊 {user.mention} размучен", ephemeral=True)


# --- /ban
@bot.tree.command(
    name="ban",
    description="Забанить пользователя навсегда с указанием причины",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь", reason="Причина")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    await user.ban(reason=reason)
    await log_action(bot, LOG_CHANNEL_ID, f"⛔ {user} забанен. Причина: {reason}")
    await interaction.response.send_message(f"⛔ {user.mention} забанен", ephemeral=True)


# --- /kick
@bot.tree.command(
    name="kick",
    description="Кикнуть пользователя с сервера с указанием причины",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь", reason="Причина")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    await user.kick(reason=reason)
    await log_action(bot, LOG_CHANNEL_ID, f"👢 {user} кикнут. Причина: {reason}")
    await interaction.response.send_message(f"👢 {user.mention} кикнут", ephemeral=True)


# --- /softban
@bot.tree.command(
    name="softban",
    description="Бан на 1 день с удалением сообщений (softban)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь", reason="Причина")
async def softban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    await user.ban(reason=reason)
    await user.unban(reason="Softban завершён")
    await log_action(bot, LOG_CHANNEL_ID, f"⚡ {user} softban на 1 день. Причина: {reason}")
    await interaction.response.send_message(f"⚡ {user.mention} softban применён", ephemeral=True)


# --- /verif
@bot.tree.command(
    name="verif",
    description="Верифицировать пользователя (снимает роль Неверифицирован, даёт Проверенный)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Пользователь, которого нужно верифицировать")
async def verif(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ Нет прав", ephemeral=True)
    guild = interaction.guild
    try:
        role_unverified = guild.get_role(ROLE_UNVERIFIED)
        role_verified = guild.get_role(ROLE_VERIFIED)
        if role_unverified in user.roles:
            await user.remove_roles(role_unverified)
        if role_verified not in user.roles:
            await user.add_roles(role_verified)
        await interaction.response.send_message(f"✅ {user.mention} успешно верифицирован!", ephemeral=True)
        await log_action(bot, LOG_CHANNEL_ID, f"✅ {user} прошёл верификацию (выдал модератор {interaction.user})")
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Ошибка: {e}", ephemeral=True)


# ==========================
#         ЗАПУСК БОТА
# ==========================
bot.run(TOKEN)

