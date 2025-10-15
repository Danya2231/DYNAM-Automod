import discord
import os, json, asyncio
from datetime import datetime, timedelta

WARN_FILE = "data/warns.json"

# =======================
#   ФУНКЦИИ ДЛЯ WARN
# =======================

def load_warns():
    if not os.path.exists(WARN_FILE):
        with open(WARN_FILE, "w") as f:
            json.dump({}, f)
    with open(WARN_FILE, "r") as f:
        return json.load(f)

def save_warns(warns):
    with open(WARN_FILE, "w") as f:
        json.dump(warns, f, indent=4)

def get_warns(user_id: int) -> int:
    warns = load_warns()
    return warns.get(str(user_id), 0)

def clear_warns(user_id: int):
    warns = load_warns()
    warns[str(user_id)] = 0
    save_warns(warns)

# =======================
#   ЛОГИ
# =======================
async def log_action(bot, log_channel_id: int, text: str):
    ch = bot.get_channel(log_channel_id)
    if ch:
        embed = discord.Embed(description=text, color=0x00ff00)
        embed.timestamp = datetime.utcnow()
        await ch.send(embed=embed)

# =======================
#   ПРИМЕНЕНИЕ НАКАЗАНИЙ
# =======================
async def apply_punishment(bot, member: discord.Member, warns_count: int):
    """Выдаёт мут или бан в зависимости от количества предупреждений"""
    guild = member.guild
    role_muted = guild.get_role(1427654016728568050)

    if warns_count == 2:
        await member.add_roles(role_muted)
        await asyncio.sleep(30*60)  # 30 минут
        await member.remove_roles(role_muted)
    elif warns_count == 3:
        await member.add_roles(role_muted)
        await asyncio.sleep(3*60*60)  # 3 часа
        await member.remove_roles(role_muted)
    elif warns_count == 4:
        await member.add_roles(role_muted)
        await asyncio.sleep(12*60*60)  # 12 часов
        await member.remove_roles(role_muted)
    elif warns_count >= 5:
        await member.ban(reason="Перевышено 5 предупреждений")

# =======================
#   ВЫДАЧА ПРЕДУПРЕЖДЕНИЯ
# =======================
async def warn_user(bot, user: discord.Member, reason: str, log_channel_id: int):
    warns = load_warns()
    uid = str(user.id)
    warns[uid] = warns.get(uid, 0) + 1
    count = warns[uid]
    save_warns(warns)

    # Отправка ЛС
    try:
        await user.send(f"⚠️ Ты получил предупреждение №{count}. Нарушение: {reason}")
    except:
        pass  # ЛС закрыты

    # Логирование
    await log_action(bot, log_channel_id, f"⚠️ {user.mention} получил предупреждение №{count}: {reason}")

    # Авто-наказание
    await apply_punishment(bot, user, count)

