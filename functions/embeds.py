import discord
import datetime
import time
import random


async def use_promo(title, content, guild_icon):
    embed = discord.Embed(colour=discord.Colour.from_rgb(240, 240, 240))

    embed.set_author(name=title)
    embed.description = content
    embed.set_image(url="https://i.gifer.com/3zt8.gif")
    embed.set_thumbnail(url=guild_icon)
    embed.set_footer(text="Приятной игры!\nВаш Sunrails Metrostroi.")

    return embed


async def swap(ctx, gold, revers, swaps):
    embed = discord.Embed(
        colour=discord.Colour.lighter_grey()
    )
    embed.description = swaps.format(ctx.author.mention, revers, "ревесивок", gold, "золотых реверсивок")
    return embed


async def server_info(guild):
    time_date = datetime.datetime.strptime(str(guild.created_at), "%Y-%m-%d %H:%M:%S.%f")

    embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 63))
    embed.set_author(name="{0.name}".format(guild))
    embed.add_field(name="Регион: ", value=str(guild.region).title())
    embed.add_field(name="ID гильдии: ", value=guild.id)
    embed.add_field(name="Системный канал: ", value="Не назначени" if not guild.system_channel
    else guild.system_channel.mention)
    embed.add_field(name="Количество участиков: ", value=guild.member_count)
    embed.add_field(name="Уровень верификации: ", value=guild.verification_level)
    embed.add_field(name="Роль по умолчанию: ", value=guild.default_role)
    embed.add_field(name="Дата создание", value=time_date.strftime("%d.%m.%Y %H:%M:%S"))
    embed.add_field(name="Лимит emoji: ", value=guild.emoji_limit)
    embed.add_field(name="Лимит участников: ", value="Безлимитно" if not guild.max_members else guild.max_members)
    embed.set_thumbnail(url=guild.icon)
    return embed


async def poll(ctx, quest, answers):
    now = datetime.datetime.now()

    simbols = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:", ":ten:"]
    things = list()

    for answer, i in zip(answers, range(0, 9)):
        things.append(f"{simbols[i]} {answer}")

    embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 63))
    embed.set_author(name=quest)
    embed.description = '\n'.join([thing for thing in things])
    embed.set_footer(text=f"Время создания: {now.strftime('%H:%M %d.%m.%Y')} | Сделал: {ctx.author.nick}")
    return embed


async def poll_time(ctx, quest, time, answers, emoji):
    now = datetime.datetime.now()
    time_end = datetime.datetime.now(datetime.timezone(datetime.timedelta(minutes=time + 180)))

    simbols = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:", ":ten:"]
    things = list()

    for answer, i in zip(answers, range(0, 9)):
        things.append(f"{simbols[i]} - {answer[0].title() + answer[1::]}")

    embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 63))
    embed.set_author(name=quest)
    for answer in answers:
        embed.add_field(name=answer[0].title() + answer[1::],
                        value=emoji,
                        inline=False)
    embed.description = '\n'.join([thing for thing in things])
    embed.set_footer(text=f"Время создания: {now.strftime('%H:%M %d.%m.%Y')} | "
                          f"Сделал: {ctx.author.name} | "
                          f"Время до окончания {time_end.strftime('%H:%M %d.%m.%Y')}")
    return embed
