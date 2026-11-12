import discord
from discord.ext import commands, tasks
import sqlite3
import time
import asyncio
import re
import random
from datetime import datetime

# --- BOT SETUP & INTENTS ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- DATENBANK SICHER INITIALISIEREN ---
db = sqlite3.connect("bot_data.db")
cursor = db.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_levels (
        user_id INTEGER,
        guild_id INTEGER,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_warns (
        user_id INTEGER,
        guild_id INTEGER,
        warn_level INTEGER,
        expire_timestamp REAL,
        PRIMARY KEY (user_id, guild_id, warn_level)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_suspensions (
        user_id INTEGER,
        guild_id INTEGER,
        expire_timestamp REAL,
        saved_roles TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_absences (
        user_id INTEGER,
        guild_id INTEGER,
        expire_timestamp REAL,
        PRIMARY KEY (user_id, guild_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bfe_officers (
        user_id INTEGER PRIMARY KEY,
        dienstnummer TEXT,
        roblox_user_name TEXT,
        rang TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reaction_roles (
        guild_id INTEGER PRIMARY KEY,
        message_id INTEGER
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS counting_game (
        channel_id INTEGER PRIMARY KEY,
        current_number INTEGER DEFAULT 1,
        last_user_id INTEGER DEFAULT 0
    )
""")
db.commit()

# --- FESTE KANAL- & KATEGORIE-IDS ---
LEVELUP_CHANNEL_ID = 1569774830952120502

CHANNEL_BEWERBUNGS_PANEL = 1569324003661840416
CHANNEL_BEWERBUNGS_ABGABE = 1569786860732162249
CHANNEL_DIENSTNUMMERN_LISTE = 1569386875108728996
CHANNEL_DIENSTNUMMERN_CHECK = 1569791658822734054

# Personal-Kanäle
CHANNEL_EINSTELLUNG = 1569621449671577650
CHANNEL_BEFOERDERUNG = 1569621599307698256
CHANNEL_DEGRADIERUNG = 1569621692651937862
CHANNEL_VERWARNUNG = 1569622019887202374
CHANNEL_SUSPENDIERUNG = 1569622266050781246
CHANNEL_ENTLASSUNG = 1569715875378888715

CHANNEL_WILLKOMMEN = 1569324003296804947
CHANNEL_VERIFY = 1569324003296804948
CHANNEL_REACTION_ROLES = 1569419964044025966
CHANNEL_ABMELDUNG = 1569980508014911562
CHANNEL_TICKET_PANEL = 1569380083901407303
CATEGORY_TICKETS = 1570113392360825023

CHANNEL_RAZZIA_LOG = 1569962986817196032
CHANNEL_DURCHSUCHUNG_LOG = 1569789398726475817
CHANNEL_RAZZIA_PANEL = 1570123076681859073

CHANNEL_REGELWERK = 1569324003296804950
CHANNEL_BUERGERRECHTE = 1569382495164567614
CHANNEL_ZAEHLEN = 1569691158676775003
CHANNEL_FUNKSTATUS = 1569984963389161492

# --- FESTE ROLLEN-IDS ---
ROLE_MITGLIED_BEWERBUNG_SPERRE = 1569410916175577319
ROLE_NICHT_VERIFIZIERT = 1569420142625165382
ROLE_TRENNUNG_BUERGER = 1569414878987292819
ROLE_BUERGER = 1569415056750285000

ROLE_ALLGEMEINE_TRENNUNG = 1569411932887457882

GROUP_1_TARGET_ROLES = {1569408817039540357, 1569404016666869910}
ROLE_GROUP_1_SEPARATOR = 1569412456399249538

GROUP_2_TARGET_ROLES = {1569410027976925327, 1569409772497805322}
ROLE_GROUP_2_SEPARATOR = 1569412653451968563

ROLE_REACTION_BASE = 1569412749723828224
ROLE_NEWS_PING = 1569413080322936894
ROLE_RP_PING = 1569413258597761135
ROLE_TEAM_UPDATES = 1569413034567532594

ROLE_TRENNUNG = 1569769035414118511
ROLE_VERWARNUNG_1 = 1569769101482524885
ROLE_VERWARNUNG_2 = 1569769241941516409
ROLE_VERWARNUNG_3 = 1569769249784864778

ROLE_SUSPENDIERT = 1569781551401668809

ROLE_LEITUNG = 1569324001858166788
ROLE_STELLV_LEITUNG = 1569324001858166787

IGNORED_ROLE_IDS = {
    ROLE_NICHT_VERIFIZIERT, ROLE_TRENNUNG_BUERGER, ROLE_BUERGER,
    ROLE_ALLGEMEINE_TRENNUNG, ROLE_GROUP_1_SEPARATOR, ROLE_GROUP_2_SEPARATOR,
    ROLE_REACTION_BASE, ROLE_NEWS_PING, ROLE_RP_PING, ROLE_TEAM_UPDATES,
    ROLE_TRENNUNG, ROLE_VERWARNUNG_1, ROLE_VERWARNUNG_2, ROLE_VERWARNUNG_3,
    ROLE_SUSPENDIERT
}

ALLOWED_VOICE_CHANNELS = {
    1569324003661840420,
    1569446445239501032,
    1569446514219294841
}


def get_real_highest_role(member: discord.Member, guild: discord.Guild) -> discord.Role:
    r_leitung = guild.get_role(ROLE_LEITUNG)
    r_stellv = guild.get_role(ROLE_STELLV_LEITUNG)
    
    if r_leitung and r_leitung in member.roles:
        return r_leitung
    if r_stellv and r_stellv in member.roles:
        return r_stellv

    valid_roles = []
    for r in member.roles:
        if r.is_default() or r.id in IGNORED_ROLE_IDS:
            continue
        if any(char in r.name for char in ["───", "---", "╭", "╮", "«", "»"]):
            continue
        valid_roles.append(r)

    if not valid_roles:
        return member.top_role
    return sorted(valid_roles, key=lambda r: r.position, reverse=True)[0]


initial_officers = [
    (1383741981812854936, "BFE-18/01", "nickmsd15", "Leitung"),
    (1382337285369892926, "BFE-18/02", "clon_10194", "Leitung"),
    (1067111639368863834, "BFE-18/03", "Philip_coool", "Stellvertretende Leitung"),
    (1203309162319183872, "BFE-18/04", "08157411billi", "Beamter"),
    (1563852013597364338, "BFE-18/05", "adram_ll2acc", "Anwärter"),
    (1431302550388211793, "BFE-18/07", "Robloxufani5", "Anwärter"),
    (1538945942643023903, "BFE-18/08", "haoasakura2000", "Anwärter")
]
for u_id, dnr, rob_user, rng in initial_officers:
    cursor.execute("""
        REPLACE INTO bfe_officers (user_id, dienstnummer, roblox_user_name, rang) 
        VALUES (?, ?, ?, ?)
    """, (u_id, dnr, rob_user, rng))
db.commit()

message_cooldowns = {}


def ist_nachtruhe() -> bool:
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    if weekday in [0, 1, 2, 3] and hour >= 22:
        return True
    if weekday in [1, 2, 3, 4] and hour < 9:
        return True
    if weekday in [4, 5, 6] and 1 <= hour < 9:
        return True
    return False


def build_screenshot_embed(guild: discord.Guild, user_id: int, dnr: str, rob_user: str) -> discord.Embed:
    member = guild.get_member(user_id)
    rob_user_clean = rob_user.lstrip("@") if rob_user else ""
    rob_at_text = f"@{rob_user_clean}" if rob_user_clean else "Unbekannt"
    
    if member:
        highest_role = get_real_highest_role(member, guild)
        role_mention_text = highest_role.mention
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    else:
        role_mention_text = "Keine Rolle"
        avatar_url = None

    embed = discord.Embed(
        title="🔎 Dienstnummer-Abfrage",
        description="✅ **Dienstnummer gefunden.**",
        color=0x0055A5
    )
    embed.add_field(name="Dienstnummer", value=f"`{dnr}`", inline=False)
    embed.add_field(name="Roblox-@-Name", value=rob_at_text, inline=False)
    embed.add_field(name="Discord-Mitglied", value=f"<@{user_id}>", inline=False)
    embed.add_field(name="Dienstgrad / Rolle", value=role_mention_text, inline=False)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text="Bundespolizei BFE+ • Dienstnummernsystem")
    return embed


async def update_dienstnummern_liste(guild: discord.Guild):
    list_channel = guild.get_channel(CHANNEL_DIENSTNUMMERN_LISTE)
    if not list_channel:
        return

    cursor.execute("SELECT dienstnummer, user_id FROM bfe_officers ORDER BY dienstnummer ASC")
    officers = cursor.fetchall()

    embed = discord.Embed(
        title="📋 BFE+ DIENSTNUMMERN-VERZEICHNIS",
        description="Offizielle Übersicht aller aktiven Einheiten und Beamten der Bundespolizei BFE+:",
        color=0x0055A5
    )

    if not officers:
        embed.add_field(name="Keine Einträge", value="Aktuell sind keine Beamten im System registriert.", inline=False)
    else:
        lines = []
        for dnr, u_id in officers:
            member = guild.get_member(u_id)
            if member:
                role_obj = get_real_highest_role(member, guild)
                role_text = role_obj.mention if role_obj else "Keine Rolle"
                lines.append(f"`{dnr}` — {member.mention} ({role_text})")
            else:
                try:
                    fetched_member = await guild.fetch_member(u_id)
                    role_obj = get_real_highest_role(fetched_member, guild)
                    role_text = role_obj.mention if role_obj else "Keine Rolle"
                    lines.append(f"`{dnr}` — {fetched_member.mention} ({role_text})")
                except Exception:
                    lines.append(f"`{dnr}` — <@{u_id}> (Nicht auf dem Server)")
        
        embed.add_field(name="Aktives Personal", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Zuletzt aktualisiert • Gesamt: {len(officers)} Beamte")

    try:
        async for message in list_channel.history(limit=10):
            if message.author == bot.user:
                await message.edit(embed=embed)
                return
        await list_channel.send(embed=embed)
    except Exception as e:
        print(f"[LISTEN FEHLER] Konnte Dienstnummern-Liste nicht aktualisieren: {e}")


@bot.event
async def on_ready():
    bot.add_view(PersonalVerwaltungsView())
    bot.add_view(BewerbungsStartView())
    bot.add_view(BewerbungsentscheidungView())
    bot.add_view(DienstnummerAbfrageView())
    bot.add_view(VerifyView())
    bot.add_view(AbmeldePanelVorschauView())
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    bot.add_view(BeschlussPanelMainView())

    print(f"Eingeloggt als {bot.user.name} (ID: {bot.user.id})")
    print("Bot ist online - Beschluss- und Managementsysteme aktiv!")

    for guild in bot.guilds:
        await update_dienstnummern_liste(guild)
    
    if not voice_xp_task.is_running():
        voice_xp_task.start()
    if not auto_expire_task.is_running():
        auto_expire_task.start()
    if not funk_curfew_task.is_running():
        funk_curfew_task.start()
    if not dienst_nickname_sync_task.is_running():
        dienst_nickname_sync_task.start()


@bot.event
async def on_raw_reaction_add(payload):
    if payload.member is None or payload.member.bot:
        return
    cursor.execute("SELECT message_id FROM reaction_roles WHERE guild_id = ?", (payload.guild_id,))
    res = cursor.fetchone()
    if not res or res[0] != payload.message_id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = payload.member
    emoji_str = str(payload.emoji)

    base_role = guild.get_role(ROLE_REACTION_BASE)
    news_role = guild.get_role(ROLE_NEWS_PING)
    rp_role = guild.get_role(ROLE_RP_PING)
    team_role = guild.get_role(ROLE_TEAM_UPDATES)

    roles_to_add = []
    if base_role:
        roles_to_add.append(base_role)
    if emoji_str == "📜" and news_role:
        roles_to_add.append(news_role)
    elif emoji_str == "🎭" and rp_role:
        roles_to_add.append(rp_role)
    elif emoji_str == "👥" and team_role:
        roles_to_add.append(team_role)

    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add)
        except Exception as e:
            print(f"[REACTION ADD FEHLER] {e}")


@bot.event
async def on_raw_reaction_remove(payload):
    cursor.execute("SELECT message_id FROM reaction_roles WHERE guild_id = ?", (payload.guild_id,))
    res = cursor.fetchone()
    if not res or res[0] != payload.message_id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    emoji_str = str(payload.emoji)
    news_role = guild.get_role(ROLE_NEWS_PING)
    rp_role = guild.get_role(ROLE_RP_PING)
    team_role = guild.get_role(ROLE_TEAM_UPDATES)
    base_role = guild.get_role(ROLE_REACTION_BASE)

    role_to_remove = None
    if emoji_str == "📜":
        role_to_remove = news_role
    elif emoji_str == "🎭":
        role_to_remove = rp_role
    elif emoji_str == "👥":
        role_to_remove = team_role

    if role_to_remove and role_to_remove in member.roles:
        try:
            await member.remove_roles(role_to_remove)
        except Exception as e:
            print(f"[REACTION REMOVE FEHLER] {e}")

    try:
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            channel = await guild.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        has_any_reaction = False
        target_emojis = ["📜", "🎭", "👥"]
        for reaction in message.reactions:
            if str(reaction.emoji) in target_emojis:
                async for reacting_user in reaction.users():
                    if reacting_user.id == member.id:
                        has_any_reaction = True
                        break
            if has_any_reaction:
                break

        if not has_any_reaction and base_role and base_role in member.roles:
            await member.remove_roles(base_role)
    except Exception as e:
        print(f"[REACTION CHECK FEHLER] {e}")


@bot.command(name="reactionpanel")
@commands.has_permissions(administrator=True)
async def reactionpanel(ctx):
    channel = ctx.guild.get_channel(CHANNEL_REACTION_ROLES)
    if not channel:
        channel = ctx.channel

    embed = discord.Embed(
        title="🔔 BUNDESPOLIZEI BFE+ — ROLLEN & BENACHRICHTIGUNGEN",
        description=(
            "Reagiere mit den entsprechenden Emojis unter dieser Nachricht, "
            "um die jeweiligen Benachrichtigungs-Rollen zu erhalten:\n\n"
            "📜 **= News Ping** (Wichtige Ankündigungen)\n"
            "🎭 **= RP Ping** (Rollenspiel-Aktivitäten & Infos)\n"
            "👥 **= Team Updates** (Einstellung, Beförderung, Degradierung, Verwarnung, Suspendierung & Entlassung)"
        ),
        color=0x0055A5
    )
    embed.set_footer(text="BFE+ Benachrichtigungssystem")
    msg = await channel.send(embed=embed)
    await msg.add_reaction("📜")
    await msg.add_reaction("🎭")
    await msg.add_reaction("👥")

    cursor.execute("REPLACE INTO reaction_roles (guild_id, message_id) VALUES (?, ?)", (ctx.guild.id, msg.id))
    db.commit()
    if channel != ctx.channel:
        await ctx.send(f"✅ Reaction-Panel erfolgreich in {channel.mention} gepostet!", delete_after=10)
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.event
async def on_member_join(member: discord.Member):
    role = member.guild.get_role(ROLE_NICHT_VERIFIZIERT)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"[BEITRITT FEHLER] {e}")

    welcome_channel = member.guild.get_channel(CHANNEL_WILLKOMMEN)
    if welcome_channel:
        embed = discord.Embed(
            title="🛡️ WILLKOMMEN BEI DER BUNDESPOLIZEI BFE+",
            description=f"Herzlich willkommen {member.mention} auf dem Server!\n\n"
                        f"Bitte verifiziere dich im Kanal <#{CHANNEL_VERIFY}>, um Zugriff auf den Server zu erhalten.",
            color=0x0055A5
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Mitglied #{member.guild.member_count} • BFE+ Personalabteilung")
        try:
            await welcome_channel.send(embed=embed)
        except Exception as e:
            print(f"[WILLKOMMEN FEHLER] {e}")


@tasks.loop(minutes=1)
async def funk_curfew_task():
    if ist_nachtruhe():
        for guild in bot.guilds:
            for vc_id in ALLOWED_VOICE_CHANNELS:
                vc = guild.get_channel(vc_id)
                if vc:
                    for member in vc.members:
                        if not member.guild_permissions.administrator:
                            try:
                                await member.move_to(None)
                                try:
                                    await member.send("🌙 **BFE+ Nachtruhe:** Die Funk-Kanäle sind zu dieser Uhrzeit geschlossen. Du wurdest getrennt.")
                                except Exception:
                                    pass
                            except Exception as e:
                                print(f"[CURFEW FEHLER] {e}")

@funk_curfew_task.before_loop
async def before_funk_curfew():
    await bot.wait_until_ready()


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in ALLOWED_VOICE_CHANNELS:
        if ist_nachtruhe() and not member.guild_permissions.administrator:
            try:
                await member.move_to(None)
                try:
                    await member.send("⛔ **Zugriff verweigert:** Zu dieser Zeit herrscht Nachtruhe im Funk!")
                except Exception:
                    pass
            except Exception:
                pass


@tasks.loop(minutes=2)
async def dienst_nickname_sync_task():
    now = time.time()
    for guild in bot.guilds:
        cursor.execute("SELECT user_id FROM active_absences WHERE guild_id = ? AND expire_timestamp <= ?", (guild.id, now))
        expired_absences = cursor.fetchall()
        for (u_id,) in expired_absences:
            cursor.execute("DELETE FROM active_absences WHERE user_id = ? AND guild_id = ?", (u_id, guild.id))
            db.commit()
            member = guild.get_member(u_id)
            if member:
                try:
                    clean_name = re.sub(r"^\[abm\]\s*", "", member.display_name, flags=re.IGNORECASE)
                    if clean_name != member.display_name:
                        await member.edit(nick=clean_name)
                    try:
                        await member.send("🟢 Deine Abwesenheit ist abgelaufen. Dein Status wurde automatisch aufgehoben.")
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[ABMELDUNG ABLAUF FEHLER] {e}")

        for member in guild.members:
            if member.bot:
                continue
            member_role_ids = {r.id for r in member.roles}
            sep_g1 = guild.get_role(ROLE_GROUP_1_SEPARATOR)
            sep_g2 = guild.get_role(ROLE_GROUP_2_SEPARATOR)
            
            has_g1_target = any(r_id in member_role_ids for r_id in GROUP_1_TARGET_ROLES)
            if has_g1_target and sep_g1 and sep_g1 not in member.roles:
                try: await member.add_roles(sep_g1)
                except Exception as e: print(f"[ROLLEN SYNC FEHLER G1]: {e}")
            elif not has_g1_target and sep_g1 and sep_g1 in member.roles:
                try: await member.remove_roles(sep_g1)
                except Exception as e: print(f"[ROLLEN REMOVE FEHLER G1]: {e}")

            has_g2_target = any(r_id in member_role_ids for r_id in GROUP_2_TARGET_ROLES)
            if has_g2_target and sep_g2 and sep_g2 not in member.roles:
                try: await member.add_roles(sep_g2)
                except Exception as e: print(f"[ROLLEN SYNC FEHLER G2]: {e}")
            elif not has_g2_target and sep_g2 and sep_g2 in member.roles:
                try: await member.remove_roles(sep_g2)
                except Exception as e: print(f"[ROLLEN REMOVE FEHLER G2]: {e}")

        cursor.execute("SELECT user_id, dienstnummer FROM bfe_officers")
        officers = cursor.fetchall()
        for u_id, dnr in officers:
            member = guild.get_member(u_id)
            if not member:
                continue
            short_dnr = dnr.replace("BFE-", "")
            cursor.execute("SELECT 1 FROM active_absences WHERE user_id = ? AND guild_id = ?", (u_id, guild.id))
            is_absent = cursor.fetchone() is not None

            current_nick = member.display_name
            base_name = re.sub(r"^\[abm\]\s*", "", current_nick, flags=re.IGNORECASE)
            base_name = re.sub(r"^\[\d+/\d+\]\s*", "", base_name)

            if is_absent:
                target_nick = f"[abm] [{short_dnr}] {base_name}"
            else:
                target_nick = f"[{short_dnr}] {base_name}"

            if len(target_nick) > 32:
                target_nick = target_nick[:32]

            if member.display_name != target_nick:
                try:
                    await member.edit(nick=target_nick)
                except Exception as e:
                    print(f"[NICKNAME SYNC FEHLER bei {member.name}]: {e}")

@dienst_nickname_sync_task.before_loop
async def before_dienst_nickname_sync():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def auto_expire_task():
    now = time.time()
    for guild in bot.guilds:
        cursor.execute("SELECT user_id, warn_level FROM active_warns WHERE guild_id = ? AND expire_timestamp <= ?", (guild.id, now))
        expired_warns = cursor.fetchall()
        for user_id, warn_level in expired_warns:
            member = guild.get_member(user_id)
            if member:
                roles_to_remove = []
                if warn_level == 1 and guild.get_role(ROLE_VERWARNUNG_1):
                    roles_to_remove.append(guild.get_role(ROLE_VERWARNUNG_1))
                elif warn_level == 2 and guild.get_role(ROLE_VERWARNUNG_2):
                    roles_to_remove.append(guild.get_role(ROLE_VERWARNUNG_2))
                elif warn_level == 3 and guild.get_role(ROLE_VERWARNUNG_3):
                    roles_to_remove.append(guild.get_role(ROLE_VERWARNUNG_3))

                cursor.execute("SELECT COUNT(*) FROM active_warns WHERE user_id = ? AND guild_id = ? AND warn_level != ?", (user_id, guild.id, warn_level))
                if cursor.fetchone()[0] == 0:
                    r_trenn = guild.get_role(ROLE_TRENNUNG)
                    if r_trenn: roles_to_remove.append(r_trenn)
                try:
                    await member.remove_roles(*roles_to_remove)
                except Exception:
                    pass
            cursor.execute("DELETE FROM active_warns WHERE user_id = ? AND guild_id = ? AND warn_level = ?", (user_id, guild.id, warn_level))

        cursor.execute("SELECT user_id, saved_roles FROM active_suspensions WHERE guild_id = ? AND expire_timestamp <= ?", (guild.id, now))
        expired_suspensions = cursor.fetchall()
        for user_id, saved_roles_str in expired_suspensions:
            member = guild.get_member(user_id)
            if member:
                roles_to_remove = [guild.get_role(ROLE_SUSPENDIERT), guild.get_role(ROLE_TRENNUNG_BUERGER), guild.get_role(ROLE_BUERGER)]
                roles_to_remove = [r for r in roles_to_remove if r and r in member.roles]
                role_ids = [int(rid) for rid in saved_roles_str.split(",") if rid.isdigit()]
                roles_to_add = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
                try:
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                    if roles_to_add:
                        await member.add_roles(*roles_to_add)
                except Exception:
                    pass
            cursor.execute("DELETE FROM active_suspensions WHERE user_id = ? AND guild_id = ?", (user_id, guild.id))
        db.commit()


@auto_expire_task.before_loop
async def before_auto_expire():
    await bot.wait_until_ready()


def add_xp(user_id: int, guild_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM user_levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    result = cursor.fetchone()
    if not result:
        cursor.execute("INSERT INTO user_levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, 0)", (user_id, guild_id, amount))
        new_xp, new_level = amount, 0
    else:
        current_xp, current_level = result
        new_xp = current_xp + amount
        new_level = current_level
        xp_needed = (current_level + 1) * 150
        if new_xp >= xp_needed:
            new_level += 1
            new_xp -= xp_needed
        cursor.execute("UPDATE user_levels SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?", (new_xp, new_level, user_id, guild_id))
    db.commit()
    return new_level, result[1] if result else 0


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # --- BEWERBUNG VIA DM ABBRECHEN ODER DURCHLAUFEN ---
    if isinstance(message.channel, discord.DMChannel):
        if message.content.strip().lower() in ["abbrechen", "cancel"]:
            if message.author.id in active_applications:
                del active_applications[message.author.id]
                await message.channel.send("❌ **Bewerbung abgebrochen.** Du kannst jederzeit über das Panel eine neue starten.")
                return
            else:
                await message.channel.send("ℹ️ Du hast aktuell keine aktive Bewerbung, die abgebrochen werden könnte.")
                return

        if message.author.id in active_applications:
            await process_application_step(message)
            return

    if not message.guild:
        return

    if message.channel.id == CHANNEL_ZAEHLEN:
        content_clean = message.content.strip()
        if content_clean.isdigit():
            eingezahl = int(content_clean)
            cursor.execute("SELECT current_number, last_user_id FROM counting_game WHERE channel_id = ?", (message.channel.id,))
            row = cursor.fetchone()
            current_target, last_user = (1, 0) if not row else row

            if message.author.id == last_user or eingezahl != current_target:
                cursor.execute("REPLACE INTO counting_game (channel_id, current_number, last_user_id) VALUES (?, 1, 0)", (message.channel.id,))
                db.commit()
                await message.add_reaction("❌")
                await message.channel.send(f"❌ **{message.author.mention} hat es vermasselt!** Die nächste Zahl ist **1**.")
                return
            else:
                next_target = current_target + 1
                cursor.execute("REPLACE INTO counting_game (channel_id, current_number, last_user_id) VALUES (?, ?, ?)", 
                               (message.channel.id, next_target, message.author.id))
                db.commit()
                await message.add_reaction("✅")
                return
        else:
            try: await message.delete()
            except Exception: pass
            return

    if message.channel.id == CHANNEL_DIENSTNUMMERN_CHECK and not message.content.startswith("!"):
        suche_clean = message.content.strip()
        cursor.execute("""
            SELECT user_id, dienstnummer, roblox_user_name 
            FROM bfe_officers 
            WHERE dienstnummer LIKE ? OR roblox_user_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
        """, (f"%{suche_clean}%", f"%{suche_clean}%", f"%{suche_clean}%"))
        result = cursor.fetchone()
        if result:
            u_id, dnr, rob_user = result
            embed = build_screenshot_embed(message.guild, u_id, dnr, rob_user)
            await message.channel.send(embed=embed, delete_after=60)
        else:
            await message.channel.send(f"❌ Kein Beamter mit dem Suchbegriff `{suche_clean}` im System gefunden.", delete_after=10)
        try: await message.delete()
        except Exception: pass
        return

    now = time.time()
    if message.author.id in message_cooldowns:
        if now - message_cooldowns[message.author.id] < 60:
            await bot.process_commands(message)
            return
    message_cooldowns[message.author.id] = now
    earned_xp = random.randint(15, 25)
    new_lvl, old_lvl = add_xp(message.author.id, message.guild.id, earned_xp)
    if new_lvl > old_lvl:
        levelup_channel = message.guild.get_channel(LEVELUP_CHANNEL_ID)
        if levelup_channel:
            try:
                await levelup_channel.send(f"🎉 Glückwunsch {message.author.mention}! Du bist im Funk & Dienst auf **Level {new_lvl}** aufgestiegen! 🎖️")
            except Exception:
                pass
    await bot.process_commands(message)


@tasks.loop(minutes=5)
async def voice_xp_task():
    for guild in bot.guilds:
        for vc_id in ALLOWED_VOICE_CHANNELS:
            vc = guild.get_channel(vc_id)
            if not vc:
                continue
            active_members = [m for m in vc.members if not m.bot and not m.voice.self_deaf]
            for member in active_members:
                new_lvl, old_lvl = add_xp(member.id, guild.id, 30)
                if new_lvl > old_lvl:
                    levelup_channel = guild.get_channel(LEVELUP_CHANNEL_ID)
                    if levelup_channel:
                        try:
                            await levelup_channel.send(f"🎉 Glückwunsch {member.mention}! Du bist im Funk & Dienst auf **Level {new_lvl}** aufgestiegen! 🎖️")
                        except Exception:
                            pass

@voice_xp_task.before_loop
async def before_voice_xp():
    await bot.wait_until_ready()


@bot.command(aliases=["check"])
async def dienstausweis(ctx, *, suche: str = None):
    if not suche:
        cursor.execute("SELECT user_id, dienstnummer, roblox_user_name FROM bfe_officers WHERE user_id = ?", (ctx.author.id,))
    else:
        suche_clean = suche.strip()
        cursor.execute("""
            SELECT user_id, dienstnummer, roblox_user_name 
            FROM bfe_officers 
            WHERE dienstnummer LIKE ? OR roblox_user_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
        """, (f"%{suche_clean}%", f"%{suche_clean}%", f"%{suche_clean}%"))
    
    result = cursor.fetchone()
    if not result:
        await ctx.send("❌ Es wurde kein Beamter mit diesen Daten im BFE+ Verzeichnis gefunden.", delete_after=10)
        return

    u_id, dnr, rob_user = result
    embed = build_screenshot_embed(ctx.guild, u_id, dnr, rob_user)
    await ctx.send(embed=embed)


@bot.command(aliases=["level", "rang"])
async def rank(ctx, member: discord.Member = None):
    if not member:
        member = ctx.author
    cursor.execute("SELECT xp, level FROM user_levels WHERE user_id = ? AND guild_id = ?", (member.id, ctx.guild.id))
    result = cursor.fetchone()
    xp, level = (0, 0) if not result else result
    xp_needed = (level + 1) * 150
    embed = discord.Embed(title=f"🛡️ DIENSTRANG-PROFIL: {member.display_name}", color=0x0055A5)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="🎖️ Level", value=f"`{level}`", inline=True)
    embed.add_field(name="⭐ XP", value=f"`{xp} / {xp_needed}`", inline=True)
    embed.set_footer(text=f"BFE+ Personalverwaltung • {ctx.guild.name}")
    await ctx.send(embed=embed)


@bot.command(aliases=["rangliste", "leaderboard"])
async def top(ctx):
    cursor.execute("SELECT user_id, level, xp FROM user_levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (ctx.guild.id,))
    top_users = cursor.fetchall()
    embed = discord.Embed(title="🏆 BFE+ DIENST-RANGLISTE", description="Die aktivsten Beamten im Chat und Funk (Top 10):", color=0xFFD700)
    if not top_users:
        embed.add_field(name="Keine Daten", value="Es sind noch keine Aktivitätsdaten vorhanden.", inline=False)
    else:
        description_lines = []
        meditations_emojis = ["🥇", "🥈", "🥉"]
        for index, (user_id, level, xp) in enumerate(top_users):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Unbekannter Beamter ({user_id})"
            rang_symbol = meditations_emojis[index] if index < 3 else f"`#{index+1}`"
            description_lines.append(f"{rang_symbol} **{name}** — Level: `{level}` (XP: `{xp}`)")
        embed.description = "\n".join(description_lines)
    embed.set_footer(text=f"Abgefragt von {ctx.author.display_name} • BFE+ Management System")
    await ctx.send(embed=embed)


@bot.command(name="update-liste")
@commands.has_permissions(administrator=True)
async def update_liste_cmd(ctx):
    await update_dienstnummern_liste(ctx.guild)
    await ctx.send("✅ Die Dienstnummern-Liste wurde erfolgreich aktualisiert!", delete_after=5)
    try: await ctx.message.delete()
    except Exception: pass


@bot.command(name="dienstgrade")
@commands.has_permissions(administrator=True)
async def dienstgrade(ctx):
    target_channel = ctx.guild.get_channel(CHANNEL_ABMELDUNG)
    if not target_channel:
        target_channel = ctx.channel

    embed = discord.Embed(
        title="🛡️ BUNDESPOLIZEI BFE+ — DIENSTGRADE & RÄNGE",
        description=(
            "Hier ist die offizielle Übersicht und Erklärung aller Ränge und Abkürzungen innerhalb der Bundespolizei BFE+:\n\n"
            "🔴 **LT** | Leitung\n"
            "🟠 **StLT** | Stv. Leitung\n"
            "🟣 **Developer** | Technik & Bot-Entwicklung\n\n"
            "═══ **« Hoher Dienst »** ═══\n"
            "🔵 **ZF** | Zugführer\n"
            "🔵 **ZF-A** | Zugführer-Anwärter\n\n"
            "═══ **« Gehobener Dienst »** ═══\n"
            "🔵 **TF** | Truppführer\n"
            "🔵 **TF-A** | Truppführer-Anwärter\n\n"
            "═══ **« Mittlerer Dienst »** ═══\n"
            "🔵 **E-BFE** | Erfahrener BFE Beamter\n"
            "🔵 **B-BFE** | BFE-Beamter\n"
            "🔵 **ANW** | BFE-Anwärter"
        ),
        color=0x0055A5
    )
    embed.set_footer(text="Bundespolizei BFE+ • Personalstruktur")

    await target_channel.send(embed=embed)
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Dienstgrad-Erklärung erfolgreich in {target_channel.mention} gesendet!", delete_after=10)
    
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="funkstatus")
@commands.has_permissions(administrator=True)
async def funkstatus(ctx):
    target_channel = ctx.guild.get_channel(CHANNEL_FUNKSTATUS)
    if not target_channel:
        target_channel = ctx.channel

    embed = discord.Embed(
        title="📡 BUNDESPOLIZEI BFE+ — OFFIZIELLER FUNKSTATUS",
        description=(
            "• **Status 1** — Einsatzbereit auf Funk\n"
            "• **Status 2** — Einsatzbereit auf Wache\n"
            "• **Status 3** — Einsatzauftrag übernommen / fahren zum Einsatz\n"
            "• **Status 4** — Ankunft an der Einsatzstelle\n"
            "• **Status 5** — Sprechwunsch\n"
            "• **Status 6** — Außer Dienst / nicht einsatzbereit (Unfall usw.)\n"
            "• **Status 7** — Patient / Gefangenen übernommen\n"
            "• **Status 8** — Ankunft am Zielort und Gefangenen abgegeben\n"
            "• **Status 9** — Verstanden / Bestätigung\n"
            "• **Status 0** — **NOTRUF**"
        ),
        color=0x0055A5
    )
    embed.set_footer(text="Bundespolizei BFE+ • Leitstellensystem")

    await target_channel.send(embed=embed)
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Funkstatus-Liste erfolgreich in {target_channel.mention} gesendet!", delete_after=10)
    
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="giveaway")
@commands.has_permissions(administrator=True)
async def giveaway(ctx, dauer_stunden: float, *, gewinn: str):
    if ctx.channel.id != 1569691575020163252:
        await ctx.send("❌ Dieser Befehl kann nur im offiziellen Giveaway-Kanal ausgeführt werden!", delete_after=10)
        try: await ctx.message.delete()
        except Exception: pass
        return

    try:
        await ctx.message.delete()
    except Exception:
        pass

    dauer_sekunden = dauer_stunden * 3600
    end_zeitpunkt = int(time.time() + dauer_sekunden)
    
    embed = discord.Embed(
        title="🎉 **GIVEAWAY** 🎉",
        description=(
            f"**Gewinn:** {gewinn}\n\n"
            f"Reagiere mit 🎉, um an der Verlosung teilzunehmen!\n\n"
            f"⏳ **Ende:** <t:{end_zeitpunkt}:R> (<t:{end_zeitpunkt}:f>)\n"
            f"👤 **Eingereicht von:** {ctx.author.mention}"
        ),
        color=0xFFD700
    )
    embed.set_footer(text="Bundespolizei BFE+ • Verlosungssystem")

    giveaway_msg = await ctx.send(embed=embed)
    await giveaway_msg.add_reaction("🎉")

    await asyncio.sleep(dauer_sekunden)

    try:
        giveaway_msg = await ctx.channel.fetch_message(giveaway_msg.id)
    except Exception:
        return

    teilnehmer = []
    for reaction in giveaway_msg.reactions:
        if str(reaction.emoji) == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    teilnehmer.append(user)
            break

    if not teilnehmer:
        embed.title = "🎉 **GIVEAWAY BEENDET** 🎉"
        embed.description = f"**Gewinn:** {gewinn}\n\n❌ **Kein Gewinner:** Niemand hat an dem Giveaway teilgenommen."
        embed.color = 0xFF0000
        await giveaway_msg.edit(embed=embed)
        await ctx.send(f"❌ Das Giveaway für **{gewinn}** ist vorbei. Es gab leider keine Teilnehmer.")
        return

    gewinner = random.choice(teilnehmer)

    embed.title = "🎉 **GIVEAWAY BEENDET** 🎉"
    embed.description = (
        f"**Gewinn:** {gewinn}\n\n"
        f"👑 **Gewinner:** {gewinner.mention}\n\n"
        f"Herzlichen Glückwunsch! Melde dich bei {ctx.author.mention}, um deinen Gewinn zu erhalten."
    )
    embed.color = 0x00FF00
    await giveaway_msg.edit(embed=embed)
    await ctx.send(f"🎉 Herzlichen Glückwunsch {gewinner.mention}! Du hast **{gewinn}** gewonnen!")


class BeschlussModal(discord.ui.Modal):
    def __init__(self, beschluss_typ: str):
        title_text = "Razzia-Beschluss erstellen" if beschluss_typ == "razzia" else "Durchsuchungsbeschluss erstellen"
        super().__init__(title=title_text)
        self.beschluss_typ = beschluss_typ

        self.wer_input = discord.ui.TextInput(
            label="Wer / Zielobjekt (z.B. Bremer Kartel)",
            placeholder="Name der Person oder Gruppierung",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.zielort_input = discord.ui.TextInput(
            label="Zielort (z.B. Werkzeugladen)",
            placeholder="Ort des Einsatzes",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.treffpunkt_input = discord.ui.TextInput(
            label="Treffpunkt",
            placeholder="z.B. KSK Gelände",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.einsatzleitung_input = discord.ui.TextInput(
            label="Einsatzleitung",
            placeholder="z.B. @LPD | 44/45 | Name",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.begruendung_input = discord.ui.TextInput(
            label="Beschlussbegründung",
            placeholder="Grund des Beschlusses / Details...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )

        self.add_item(self.wer_input)
        self.add_item(self.zielort_input)
        self.add_item(self.treffpunkt_input)
        self.add_item(self.einsatzleitung_input)
        self.add_item(self.begruendung_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        if self.beschluss_typ == "razzia":
            titel = "📄 · RAZZIA-BESCHLUSS"
            target_channel = guild.get_channel(CHANNEL_RAZZIA_LOG)
        else:
            titel = "🔍 · DURCHSUCHUNGSBESCHLUSS"
            target_channel = guild.get_channel(CHANNEL_DURCHSUCHUNG_LOG)

        if not target_channel:
            target_channel = interaction.channel

        begruendung_text = self.begruendung_input.value.strip()

        embed = discord.Embed(title=titel, color=0x2B2D31)
        embed.description = (
            f"```yaml\n"
            f"Wer: {self.wer_input.value.strip()}\n"
            f"Zielort: {self.zielort_input.value.strip()}\n"
            f"```\n"
            f"**Treffpunkt:** {self.treffpunkt_input.value.strip()}\n"
            f"**Einsatzleitung:** {self.einsatzleitung_input.value.strip()}\n"
            f"**Genehmigt von:** {interaction.user.mention}\n\n"
            f"────────────────────────\n\n"
            f"📋 **· BESCHLUSSBEGRÜNDUNG**\n"
            f"> {begruendung_text}"
        )

        await target_channel.send(embed=embed)
        await interaction.followup.send(f"✅ Beschluss erfolgreich erstellt und in {target_channel.mention} gepostet!", ephemeral=True)


class BeschlussPanelMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Razzia-Beschluss erstellen", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="btn_create_razzia")
    async def create_razzia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BeschlussModal("razzia"))

    @discord.ui.button(label="Durchsuchungsbeschluss erstellen", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="btn_create_durchsuchung")
    async def create_durchsuchung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BeschlussModal("durchsuchung"))


@bot.command(name="beschluss-panel")
@commands.has_permissions(administrator=True)
async def beschluss_panel(ctx):
    embed = discord.Embed(
        title="🛡️ BUNDESPOLIZEI BFE+ — BESCHLUSSSYSTEM",
        description="Klicke auf den entsprechenden Button unten, um einen offiziellen **Razzia-Beschluss** oder **Durchsuchungsbeschluss** zu erstellen.",
        color=0x0055A5
    )
    embed.set_footer(text="Bundespolizei BFE+ • Einsatzleitung & Recht")

    channel = ctx.guild.get_channel(CHANNEL_RAZZIA_PANEL)
    target_channel = channel if channel else ctx.channel
    await target_channel.send(embed=embed, view=BeschlussPanelMainView())

    try: await ctx.message.delete()
    except Exception: pass


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 **Ticket wird in 5 Sekunden geschlossen...**", ephemeral=False)
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except Exception as e: print(f"[TICKET LÖSCHEN FEHLER]: {e}")


class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Allgemeine Fragen", description="Fragen rund um den Server & Einheiten", emoji="❓", value="allgemein"),
            discord.SelectOption(label="Beschwerde", description="Melde ein Problem oder Fehlverhalten", emoji="⚠️", value="beschwerde"),
            discord.SelectOption(label="Leitungsebene", description="Wichtige Anliegen direkt an die Leitung", emoji="👑", value="leitung")
        ]
        super().__init__(placeholder="Wähle eine Ticket-Kategorie aus...", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        category = guild.get_channel(CATEGORY_TICKETS)

        ticket_type = self.values[0]
        type_names = {"allgemein": "allgemeine-frage", "beschwerde": "beschwerde", "leitung": "leitungsebene"}
        channel_name = f"ticket-{type_names.get(ticket_type, 'support')}-{member.name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        if ticket_type == "leitung":
            r_leitung = guild.get_role(ROLE_LEITUNG)
            r_stellv = guild.get_role(ROLE_STELLV_LEITUNG)
            if r_leitung: overwrites[r_leitung] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            if r_stellv: overwrites[r_stellv] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites
            )

            embed = discord.Embed(
                title=f"🎫 Ticket: {self.values[0].capitalize()}",
                description=f"Hallo {member.mention},\n\nVielen Dank für dein Ticket. Ein Teammitglied wird sich in Kürze darum kümmern.\nKlicke unten, um das Ticket zu schließen.",
                color=0x0055A5
            )
            embed.set_footer(text="Bundespolizei BFE+ • Ticketsystem")
            await ticket_channel.send(embed=embed, view=TicketCloseView())
            await interaction.response.send_message(f"✅ Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Fehler beim Erstellen des Tickets: `{e}`", ephemeral=True)


class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


@bot.command(name="ticketpanel")
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = discord.Embed(title="🎫 TICKETSYSTEM", description="Wähle eine Kategorie aus:", color=0x0055A5)
    channel = ctx.guild.get_channel(CHANNEL_TICKET_PANEL)
    await (channel if channel else ctx.channel).send(embed=embed, view=TicketSelectView())
    try: await ctx.message.delete()
    except Exception: pass


class AbmeldungModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Dienstabmeldung")
        self.datum_von = discord.ui.TextInput(label="Datum von", placeholder="TT.MM.", style=discord.TextStyle.short, required=True)
        self.datum_bis = discord.ui.TextInput(label="Datum bis", placeholder="TT.MM.", style=discord.TextStyle.short, required=True)
        self.uhrzeit_von = discord.ui.TextInput(label="Uhrzeit von", placeholder="HH:MM", style=discord.TextStyle.short, required=True)
        self.uhrzeit_bis = discord.ui.TextInput(label="Uhrzeit bis", placeholder="HH:MM", style=discord.TextStyle.short, required=True)
        self.add_item(self.datum_von)
        self.add_item(self.datum_bis)
        self.add_item(self.uhrzeit_von)
        self.add_item(self.uhrzeit_bis)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        expire_time = time.time() + (7 * 86400)
        cursor.execute("REPLACE INTO active_absences (user_id, guild_id, expire_timestamp) VALUES (?, ?, ?)", (member.id, guild.id, expire_time))
        db.commit()
        try:
            current_nick = member.display_name
            base_name = re.sub(r"^\[abm\]\s*", "", current_nick, flags=re.IGNORECASE)
            cursor.execute("SELECT dienstnummer FROM bfe_officers WHERE user_id = ?", (member.id,))
            row = cursor.fetchone()
            if row:
                short_dnr = row[0].replace("BFE-", "")
                base_name = re.sub(r"^\[\d+/\d+\]\s*", "", base_name)
                new_nick = f"[abm] [{short_dnr}] {base_name}"
            else:
                new_nick = f"[abm] {base_name}"
            if len(new_nick) > 32: new_nick = new_nick[:32]
            await member.edit(nick=new_nick)
        except Exception:
            pass
        await interaction.followup.send("✅ Abmeldung erfolgreich eingereicht!", ephemeral=True)


class AbmeldePanelVorschauView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abmelden", style=discord.ButtonStyle.primary, emoji="🏖️", custom_id="btn_abmelden_start")
    async def abmelden_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AbmeldungModal())


@bot.command(name="abmelde-panel")
@commands.has_permissions(administrator=True)
async def abmelde_panel(ctx):
    embed = discord.Embed(title="🏖️ DIENSTABMELDUNG", description="Klicke hier, um dich abzumelden.", color=0x0055A5)
    channel = ctx.guild.get_channel(CHANNEL_ABMELDUNG)
    await (channel if channel else ctx.channel).send(embed=embed, view=AbmeldePanelVorschauView())
    try: await ctx.message.delete()
    except Exception: pass


@bot.command(name="regelwerk")
@commands.has_permissions(administrator=True)
async def regelwerk_senden(ctx):
    kanal = ctx.guild.get_channel(CHANNEL_REGELWERK)
    if kanal: await kanal.send("📜 **Dienstregelwerk BFE+**")
    try: await ctx.message.delete()
    except Exception: pass


@bot.command(name="server-regelwerk")
@commands.has_permissions(administrator=True)
async def server_regelwerk_senden(ctx):
    kanal = ctx.guild.get_channel(CHANNEL_REGELWERK)
    if kanal: await kanal.send("📜 **Discord-Server-Regelwerk**")
    try: await ctx.message.delete()
    except Exception: pass


@bot.command(name="buergerrechte")
@commands.has_permissions(administrator=True)
async def buergerrechte_senden(ctx):
    kanal = ctx.guild.get_channel(CHANNEL_BUERGERRECHTE)
    if kanal: await kanal.send("🛡️ **Bürgerrechte**")
    try: await ctx.message.delete()
    except Exception: pass


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verifizieren", style=discord.ButtonStyle.success, emoji="✅", custom_id="btn_verify_click")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role_unverified = guild.get_role(ROLE_NICHT_VERIFIZIERT)
        role_buerger = guild.get_role(ROLE_BUERGER)
        role_trenn_buerger = guild.get_role(ROLE_TRENNUNG_BUERGER)  # Die wichtige Trennungsrolle für Besucher/Bürger
        
        if role_unverified and role_unverified in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role_unverified)
                roles_to_add = [r for r in [role_buerger, role_trenn_buerger] if r]
                if roles_to_add:
                    await interaction.user.add_roles(*roles_to_add)
                await interaction.response.send_message("✅ Verifiziert! Du hast nun Zugriff auf den Server.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"⚠️ Fehler: `{e}`", ephemeral=True)
        else:
            # Falls sie die Rolle schon haben aber die Trennungsrolle fehlt, sicherheitshalber nachrüsten
            try:
                if role_trenn_buerger and role_trenn_buerger not in interaction.user.roles:
                    await interaction.user.add_roles(role_trenn_buerger)
            except Exception:
                pass
            await interaction.response.send_message("ℹ️ Du bist bereits verifiziert!", ephemeral=True)


@bot.command(name="verify-panel")
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    embed = discord.Embed(title="🛡️ VERIFIZIERUNG", description="Klicke zum Verifizieren.", color=0x0055A5)
    verify_channel = ctx.guild.get_channel(CHANNEL_VERIFY)
    await (verify_channel if verify_channel else ctx.channel).send(embed=embed, view=VerifyView())
    try: await ctx.message.delete()
    except Exception: pass


class DienstnummerModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Dienstnummer-Abfrage")
        self.dnr_input = discord.ui.TextInput(label="Dienstnummer", placeholder="BFE-18/01", style=discord.TextStyle.short, required=True)
        self.add_item(self.dnr_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        suche_clean = self.dnr_input.value.strip()
        cursor.execute("SELECT user_id, dienstnummer, roblox_user_name FROM bfe_officers WHERE dienstnummer LIKE ? OR roblox_user_name LIKE ?", (f"%{suche_clean}%", f"%{suche_clean}%"))
        result = cursor.fetchone()
        if result:
            u_id, dnr, rob_user = result
            embed = build_screenshot_embed(interaction.guild, u_id, dnr, rob_user)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Nicht gefunden.", ephemeral=True)


class DienstnummerAbfrageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Dienstnummer abfragen", style=discord.ButtonStyle.primary, emoji="🔎", custom_id="btn_dienstnummer_abfragen")
    async def abfragen_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DienstnummerModal())


@bot.command()
@commands.has_permissions(administrator=True)
async def abfragepanel(ctx):
    embed = discord.Embed(title="🔎 ABFRAGE", description="Klicke hier.", color=0x0055A5)
    await ctx.send(embed=embed, view=DienstnummerAbfrageView())
    try: await ctx.message.delete()
    except Exception: pass


# =========================================================================
# BEWERBUNGSSYSTEM MIT ABBRECH-FUNKTION IN DM
# =========================================================================
active_applications = {}

async def process_application_step(message: discord.Message):
    user_id = message.author.id
    data = active_applications[user_id]
    step = data["step"]

    if step == 1:
        data["answers"]["roblox"] = message.content.strip()
        data["step"] = 2
        await message.channel.send("📝 **Frage 2/3:** Warum möchtest du der Bundespolizei BFE+ beitreten? *(Schreibe 'abbrechen', um die Bewerbung jederzeit zu beenden)*")
    elif step == 2:
        data["answers"]["warum"] = message.content.strip()
        data["step"] = 3
        await message.channel.send("📝 **Frage 3/3:** Hast du bereits Vorerfahrung im Bereich RP/Polizei? *(Schreibe 'abbrechen', um die Bewerbung jederzeit zu beenden)*")
    elif step == 3:
        data["answers"]["erfahrung"] = message.content.strip()
        guild = bot.get_guild(data["guild_id"])
        if guild:
            abgabe_kanal = guild.get_channel(CHANNEL_BEWERBUNGS_ABGABE)
            if abgabe_kanal:
                embed = discord.Embed(
                    title="🛡️ NEUE BEWERBUNG EINGEGANGEN",
                    description=f"**Bewerber:** {message.author.mention} (`{message.author.id}`)",
                    color=0x0055A5
                )
                embed.add_field(name="Roblox-Name", value=data["answers"]["roblox"], inline=False)
                embed.add_field(name="Warum BFE+?", value=data["answers"]["warum"], inline=False)
                embed.add_field(name="Vorerfahrung", value=data["answers"]["erfahrung"], inline=False)
                embed.set_footer(text=f"User ID: {message.author.id}")
                await abgabe_kanal.send(embed=embed, view=BewerbungsentscheidungView())
        
        await message.channel.send("✅ **Deine Bewerbung wurde erfolgreich eingereicht!** Ein Teammitglied wird sich in Kürze bei dir melden.")
        del active_applications[user_id]


class AnnahmeModal(discord.ui.Modal):
    def __init__(self, applicant_member: discord.Member):
        super().__init__(title="Annahme")
        self.applicant_member = applicant_member
        self.roblox_user_input = discord.ui.TextInput(label="Roblox-Name", placeholder="@Name", style=discord.TextStyle.short, required=True)
        self.add_item(self.roblox_user_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        rob_user = self.roblox_user_input.value.strip()
        r_mitglied = guild.get_role(ROLE_MITGLIED_BEWERBUNG_SPERRE)
        r_anwaerter = guild.get_role(1569408615054315641)
        try:
            if r_mitglied: await self.applicant_member.add_roles(r_mitglied)
            if r_anwaerter: await self.applicant_member.add_roles(r_anwaerter)
        except Exception:
            pass
        cursor.execute("SELECT COUNT(*) FROM bfe_officers")
        count = cursor.fetchone()[0] + 1
        dnr = f"BFE-18/{count:02d}"
        cursor.execute("REPLACE INTO bfe_officers (user_id, dienstnummer, roblox_user_name, rang) VALUES (?, ?, ?, ?)", (self.applicant_member.id, dnr, rob_user, "Anwärter"))
        db.commit()
        await update_dienstnummern_liste(guild)

        einstellungs_kanal = guild.get_channel(CHANNEL_EINSTELLUNG)
        if einstellungs_kanal:
            embed = discord.Embed(
                title="📋 PERSONALMELDUNG — EINSTELLUNG",
                description=f"Herzlich willkommen {self.applicant_member.mention} bei der **Bundespolizei BFE+**!",
                color=0x00CC66
            )
            embed.add_field(name="Dienstnummer", value=f"`{dnr}`", inline=True)
            embed.add_field(name="Dienstgrad", value="Anwärter", inline=True)
            embed.add_field(name="Roblox-Name", value=rob_user, inline=True)
            embed.set_footer(text=f"Eingestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await einstellungs_kanal.send(embed=embed)

        try:
            await self.applicant_member.send(f"🎉 **Herzlichen Glückwunsch!** Deine Bewerbung bei der Bundespolizei BFE+ wurde angenommen! Deine Dienstnummer lautet **`{dnr}`**.")
        except Exception:
            pass

        await interaction.followup.send(f"✅ Angenommen als `{dnr}` und in <#{CHANNEL_EINSTELLUNG}> eingetragen!", ephemeral=True)


class BewerbungsentscheidungView(discord.ui.View):
    def __init__(self, applicant_id: int = None):
        super().__init__(timeout=None)

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, emoji="✅", custom_id="btn_bewerbung_annehmen")
    async def annehmen(self, interaction: discord.Interaction, button: discord.ui.Button):
        footer_text = interaction.message.embeds[0].footer.text if interaction.message.embeds else ""
        match = re.search(r"User ID: (\d+)", footer_text)
        if not match: return
        applicant_member = interaction.guild.get_member(int(match.group(1))) or await interaction.guild.fetch_member(int(match.group(1)))
        await interaction.response.send_modal(AnnahmeModal(applicant_member))

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, emoji="❌", custom_id="btn_bewerbung_ablehnen")
    async def ablehnen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = interaction.message.embeds[0]
        embed.color = 0xFF0000
        embed.add_field(name="Status", value="❌ **Abgelehnt**", inline=False)
        await interaction.message.edit(embed=embed, view=self)


class BewerbungsStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bewerbung einreichen", style=discord.ButtonStyle.success, emoji="📝", custom_id="btn_bewerbung_start")
    async def bewerbung_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in active_applications:
            await interaction.response.send_message("⚠️ Du hast bereits eine laufende Bewerbung in deinen DMs! Schreibe dort **abbrechen**, wenn du sie neu starten möchtest.", ephemeral=True)
            return

        active_applications[user_id] = {
            "guild_id": interaction.guild.id,
            "step": 1,
            "answers": {}
        }

        try:
            await interaction.user.send("📬 **Bewerbung bei der Bundespolizei BFE+ gestartet!**\n\n📝 **Frage 1/3:** Wie lautet dein Roblox-Benutzername?\n*(Du kannst diese Bewerbung jederzeit abbrechen, indem du hier **abbrechen** schreibst.)*")
            await interaction.response.send_message("✅ Ich habe dir eine Nachricht in deinen Direktnachrichten (DMs) geschickt!", ephemeral=True)
        except Exception:
            del active_applications[user_id]
            await interaction.response.send_message("❌ Konnte dir keine DM senden. Bitte aktiviere Direktnachrichten von Servermitgliedern.", ephemeral=True)


@bot.command()
@commands.has_permissions(administrator=True)
async def bewerbungspanel(ctx):
    embed = discord.Embed(title="🛡️ BEWERBUNG", description="Klicke zum Bewerben.", color=0x0055A5)
    channel = ctx.guild.get_channel(CHANNEL_BEWERBUNGS_PANEL)
    await (channel if channel else ctx.channel).send(embed=embed, view=BewerbungsStartView())
    try: await ctx.message.delete()
    except Exception: pass


# =========================================================================
# PERSONALVERWALTUNG (BEFÖRDERUNG, DEGRADIERUNG, VERWARNUNG, SUSPENDIERUNG, ENTLASSUNG)
# =========================================================================
class PersonalMassnahmeModal(discord.ui.Modal):
    def __init__(self, massnahme_typ: str):
        titles = {
            "befoerderung": "Beamten befördern",
            "degradierung": "Beamten degradieren",
            "abmahnung": "Verwarnung / Abmahnung erteilen",
            "suspendierung": "Beamten suspendieren",
            "entlassung": "Beamten entlassen"
        }
        super().__init__(title=titles.get(massnahme_typ, "Personalmaßnahme"))
        self.massnahme_typ = massnahme_typ

        self.user_id_input = discord.ui.TextInput(
            label="Discord User-ID des Beamten",
            placeholder="z.B. 1203309162319183872",
            style=discord.TextStyle.short,
            required=True,
            max_length=25
        )
        self.add_item(self.user_id_input)

        if massnahme_typ in ["befoerderung", "degradierung"]:
            self.rang_input = discord.ui.TextInput(
                label="Neuer Dienstgrad / Rang",
                placeholder="z.B. BFE-Beamter, Truppführer, Zugführer...",
                style=discord.TextStyle.short,
                required=True,
                max_length=50
            )
            self.add_item(self.rang_input)

        if massnahme_typ == "abmahnung":
            self.warn_stufe_input = discord.ui.TextInput(
                label="Verwarnungsstufe (1, 2 oder 3)",
                placeholder="1",
                style=discord.TextStyle.short,
                required=True,
                max_length=1
            )
            self.add_item(self.warn_stufe_input)

        if massnahme_typ == "suspendierung":
            self.dauer_tage_input = discord.ui.TextInput(
                label="Dauer der Suspendierung (in Tagen)",
                placeholder="z.B. 3",
                style=discord.TextStyle.short,
                required=True,
                max_length=3
            )
            self.add_item(self.dauer_tage_input)

        self.grund_input = discord.ui.TextInput(
            label="Begründung / Bemerkung",
            placeholder="Grund für die Personalmaßnahme...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=400
        )
        self.add_item(self.grund_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        raw_id = re.sub(r"\D", "", self.user_id_input.value.strip())
        if not raw_id.isdigit():
            await interaction.followup.send("❌ Ungültige User-ID eingegeben.", ephemeral=True)
            return

        target_id = int(raw_id)
        member = guild.get_member(target_id)
        if not member:
            try:
                member = await guild.fetch_member(target_id)
            except Exception:
                member = None

        target_mention = member.mention if member else f"<@{target_id}>"
        grund = self.grund_input.value.strip()

        if self.massnahme_typ == "befoerderung":
            neuer_rang = self.rang_input.value.strip()
            cursor.execute("UPDATE bfe_officers SET rang = ? WHERE user_id = ?", (neuer_rang, target_id))
            db.commit()
            await update_dienstnummern_liste(guild)

            log_channel = guild.get_channel(CHANNEL_BEFOERDERUNG) or interaction.channel
            embed = discord.Embed(
                title="📈 PERSONALMELDUNG — BEFÖRDERUNG",
                description=f"Hiermit wird {target_mention} mit sofortiger Wirkung in den Dienstgrad **{neuer_rang}** befördert!",
                color=0x00CC66
            )
            embed.add_field(name="Begründung", value=grund, inline=False)
            embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await log_channel.send(embed=embed)
            if member:
                try: await member.send(f"🎉 **Herzlichen Glückwunsch!** Du wurdest bei der Bundespolizei BFE+ zum **{neuer_rang}** befördert!\n**Grund:** {grund}")
                except Exception: pass
            await interaction.followup.send(f"✅ Beförderung für {target_mention} in {log_channel.mention} gepostet!", ephemeral=True)

        elif self.massnahme_typ == "degradierung":
            neuer_rang = self.rang_input.value.strip()
            cursor.execute("UPDATE bfe_officers SET rang = ? WHERE user_id = ?", (neuer_rang, target_id))
            db.commit()
            await update_dienstnummern_liste(guild)

            log_channel = guild.get_channel(CHANNEL_DEGRADIERUNG) or interaction.channel
            embed = discord.Embed(
                title="📉 PERSONALMELDUNG — DEGRADIERUNG",
                description=f"Hiermit wird {target_mention} mit sofortiger Wirkung in den Dienstgrad **{neuer_rang}** degradiert.",
                color=0xFF9900
            )
            embed.add_field(name="Begründung", value=grund, inline=False)
            embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await log_channel.send(embed=embed)
            if member:
                try: await member.send(f"⚠️ **Dienstliche Mitteilung:** Du wurdest bei der Bundespolizei BFE+ auf den Rang **{neuer_rang}** degradiert.\n**Grund:** {grund}")
                except Exception: pass
            await interaction.followup.send(f"✅ Degradierung für {target_mention} in {log_channel.mention} gepostet!", ephemeral=True)

        elif self.massnahme_typ == "abmahnung":
            stufe_str = self.warn_stufe_input.value.strip()
            stufe = int(stufe_str) if stufe_str in ["1", "2", "3"] else 1
            expire_ts = time.time() + (14 * 86400)
            cursor.execute("REPLACE INTO active_warns (user_id, guild_id, warn_level, expire_timestamp) VALUES (?, ?, ?, ?)",
                           (target_id, guild.id, stufe, expire_ts))
            db.commit()

            if member:
                role_map = {1: ROLE_VERWARNUNG_1, 2: ROLE_VERWARNUNG_2, 3: ROLE_VERWARNUNG_3}
                r_warn = guild.get_role(role_map[stufe])
                r_trenn = guild.get_role(ROLE_TRENNUNG)
                roles_to_add = [r for r in [r_trenn, r_warn] if r]
                if roles_to_add:
                    try: await member.add_roles(*roles_to_add)
                    except Exception: pass

            log_channel = guild.get_channel(CHANNEL_VERWARNUNG) or interaction.channel
            embed = discord.Embed(
                title=f"⚠️ PERSONALMELDUNG — VERWARNUNG (STUFE {stufe})",
                description=f"Hiermit erhält {target_mention} eine offizielle **Verwarnung (Stufe {stufe})**.",
                color=0xFFCC00
            )
            embed.add_field(name="Begründung", value=grund, inline=False)
            embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await log_channel.send(embed=embed)
            if member:
                try: await member.send(f"⚠️ **Dienstliche Verwarnung (Stufe {stufe}):** Du hast bei der Bundespolizei BFE+ eine Verwarnung erhalten.\n**Grund:** {grund}")
                except Exception: pass
            await interaction.followup.send(f"✅ Verwarnung (Stufe {stufe}) für {target_mention} in {log_channel.mention} gepostet!", ephemeral=True)

        elif self.massnahme_typ == "suspendierung":
            tage_str = re.sub(r"\D", "", self.dauer_tage_input.value.strip())
            tage = int(tage_str) if tage_str.isdigit() and int(tage_str) > 0 else 3
            expire_ts = time.time() + (tage * 86400)

            saved_role_ids = []
            if member:
                for r in member.roles:
                    if not r.is_default() and r.id not in [ROLE_SUSPENDIERT, ROLE_TRENNUNG_BUERGER, ROLE_BUERGER]:
                        saved_role_ids.append(str(r.id))
                roles_to_remove = [guild.get_role(int(rid)) for rid in saved_role_ids if guild.get_role(int(rid))]
                r_susp = guild.get_role(ROLE_SUSPENDIERT)
                r_trenn_b = guild.get_role(ROLE_TRENNUNG_BUERGER)
                r_buerger = guild.get_role(ROLE_BUERGER)
                roles_to_add = [r for r in [r_susp, r_trenn_b, r_buerger] if r]
                try:
                    if roles_to_remove: await member.remove_roles(*roles_to_remove)
                    if roles_to_add: await member.add_roles(*roles_to_add)
                except Exception:
                    pass

            cursor.execute("REPLACE INTO active_suspensions (user_id, guild_id, expire_timestamp, saved_roles) VALUES (?, ?, ?, ?)",
                           (target_id, guild.id, expire_ts, ",".join(saved_role_ids)))
            db.commit()

            log_channel = guild.get_channel(CHANNEL_SUSPENDIERUNG) or interaction.channel
            embed = discord.Embed(
                title="⛔ PERSONALMELDUNG — SUSPENDIERUNG",
                description=f"Hiermit wird {target_mention} für **{tage} Tag(e)** vom Dienst **suspendiert**.",
                color=0xE67E22
            )
            embed.add_field(name="Dauer", value=f"{tage} Tag(e) (bis <t:{int(expire_ts)}:f>)", inline=False)
            embed.add_field(name="Begründung", value=grund, inline=False)
            embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await log_channel.send(embed=embed)
            if member:
                try: await member.send(f"⛔ **Suspendierungsmitteilung:** Du wurdest für **{tage} Tag(e)** vom Dienst bei der Bundespolizei BFE+ suspendiert.\n**Grund:** {grund}")
                except Exception: pass
            await interaction.followup.send(f"✅ Suspendierung für {target_mention} in {log_channel.mention} gepostet!", ephemeral=True)

        elif self.massnahme_typ == "entlassung":
            cursor.execute("DELETE FROM bfe_officers WHERE user_id = ?", (target_id,))
            db.commit()
            await update_dienstnummern_liste(guild)

            if member:
                roles_to_remove = [r for r in member.roles if not r.is_default() and r.id != ROLE_BUERGER]
                try:
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                    r_buerger = guild.get_role(ROLE_BUERGER)
                    r_trenn_buerger = guild.get_role(ROLE_TRENNUNG_BUERGER)
                    if r_buerger and r_buerger not in member.roles:
                        await member.add_roles(r_buerger)
                    if r_trenn_buerger and r_trenn_buerger not in member.roles:
                        await member.add_roles(r_trenn_buerger)
                    clean_nick = re.sub(r"^(\[abm\]\s*)?(\[\d+/\d+\]\s*)?", "", member.display_name, flags=re.IGNORECASE)
                    if clean_nick != member.display_name:
                        await member.edit(nick=clean_nick)
                except Exception:
                    pass

            log_channel = guild.get_channel(CHANNEL_ENTLASSUNG) or interaction.channel
            embed = discord.Embed(
                title="🚪 PERSONALMELDUNG — ENTLASSUNG",
                description=f"Hiermit wird {target_mention} mit sofortiger Wirkung aus dem Dienst der Bundespolizei BFE+ **entlassen**.",
                color=0xFF0000
            )
            embed.add_field(name="Begründung", value=grund, inline=False)
            embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bundespolizei BFE+")
            await log_channel.send(embed=embed)
            if member:
                try: await member.send(f"🚪 **Entlassungsmitteilung:** Du wurdest aus dem Dienst der Bundespolizei BFE+ entlassen.\n**Grund:** {grund}")
                except Exception: pass
            await interaction.followup.send(f"✅ Entlassung für {target_mention} in {log_channel.mention} gepostet!", ephemeral=True)


class PersonalVerwaltungsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Beförderung", style=discord.ButtonStyle.success, emoji="📈", custom_id="btn_personal_befoerderung")
    async def btn_befoerderung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonalMassnahmeModal("befoerderung"))

    @discord.ui.button(label="Degradierung", style=discord.ButtonStyle.secondary, emoji="📉", custom_id="btn_personal_degradierung")
    async def btn_degradierung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonalMassnahmeModal("degradierung"))

    @discord.ui.button(label="Verwarnung", style=discord.ButtonStyle.primary, emoji="⚠️", custom_id="btn_personal_abmahnung")
    async def btn_abmahnung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonalMassnahmeModal("abmahnung"))

    @discord.ui.button(label="Suspendierung", style=discord.ButtonStyle.secondary, emoji="⛔", custom_id="btn_personal_suspendierung")
    async def btn_suspendierung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonalMassnahmeModal("suspendierung"))

    @discord.ui.button(label="Entlassung", style=discord.ButtonStyle.danger, emoji="🚪", custom_id="btn_personal_entlassung")
    async def btn_entlassung(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonalMassnahmeModal("entlassung"))


@bot.command()
@commands.has_permissions(manage_roles=True)
async def verwaltung(ctx):
    embed = discord.Embed(
        title="⚙️ BFE+ PERSONALVERWALTUNG",
        description=(
            "Wähle unten eine der Personalmaßnahmen aus, um das entsprechende Formular zu öffnen:\n\n"
            "📈 **Beförderung** — Beamten auf einen höheren Rang befördern\n"
            "📉 **Degradierung** — Beamten auf einen niedrigeren Rang herabstufen\n"
            "⚠️ **Verwarnung** — Offizielle Verwarnung (Stufe 1–3) aussprechen\n"
            "⛔ **Suspendierung** — Beamten temporär vom Dienst suspendieren\n"
            "🚪 **Entlassung** — Beamten aus dem Dienst entfernen"
        ),
        color=0x0055A5
    )
    embed.set_footer(text="Bundespolizei BFE+ • Leitungs- & Personalpanel")
    await ctx.send(embed=embed, view=PersonalVerwaltungsView())
    try: await ctx.message.delete()
    except Exception: pass


# BOT-TOKEN HIER EINTRAGEN
bot.run("MTU2OTQyMDYzMzkzMzIxNzgzMw.G-SRRd.jJrZBlsSXNDmo4CY3zlRNY2m-P3sJAWTCBfdy4")