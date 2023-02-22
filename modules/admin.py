#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import asyncio
import shutil

import discord

from utils.models import *
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import Union, Optional, Literal

from main import Katherine, AbstractCog
from utils.context import Context


class ModalChoiceTime(discord.ui.Modal, title="Создание голосования"):
    time_on_poll = discord.ui.TextInput(
        label="Время голосование (в мин.)",
        style=discord.TextStyle.short,
        placeholder="Введите число минут, в течении которых будет идти голосование",
        required=True
    )

    question = discord.ui.TextInput(
        label="Вопрос",
        style=discord.TextStyle.long,
        required=True
    )

    answers = discord.ui.TextInput(
        label="Ответы",
        placeholder="Вариант ответа должен писаться через +",
        default="+Да +Нет +Ляписа ответ",
        style=discord.TextStyle.long,
        required=True
    )

    def __init__(self):
        super(ModalChoiceTime, self).__init__(timeout=15.0)
        self.choice_on: bool = False

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if not self.time_on_poll.value.isdigit():
            await interaction.response.send_message("Время должно быть числом", ephemeral=True)
            return False
        elif int(self.time_on_poll.value) > 60:
            await interaction.response.send_message("Кол-во минут не должно превышать 60!", ephemeral=True)
            return False
        else:
            await interaction.response.defer()
            return True

    async def on_submit(self, interaction: discord.Interaction, /) -> Optional[Union[discord.Embed, None]]:
        answers = self.answers.value.split("+")[1::]
        bot: Katherine = interaction.client  # noqa

        if len(answers) > 9 or len(answers) < 1:
            await interaction.response.send_message(
                embed=await bot.embed(f"Ответов очень {'мало' if len(answers) < 1 else 'много'}.",
                                      f"Голосование не может быть создано, потому что количество "
                                      f"ответов {'меньше 1' if len(answers) < 1 else 'больше 9'}."),
                ephemeral=True)
            return

        emoji = "✅"

        now = datetime.now()
        time_end = datetime.now(timezone(timedelta(minutes=int(self.time_on_poll.value) + 180)))

        simbols = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:",
                   ":seven:", ":eight:", ":nine:", ":ten:"]  # noqa
        things = list()

        for answer, i in zip(answers, range(0, len(answers))):
            things.append(f"{simbols[i]} - {answer[0].title() + answer[1::]}")

        embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 63))
        embed.set_author(name=self.question.value)

        for answer in answers:  # noqa
            embed.add_field(name=answer[0].title() + answer[1::],
                            value=emoji,
                            inline=False)
        embed.description = '\n'.join([thing for thing in things])
        embed.set_footer(text=f"Время создания: {now.strftime('%H:%M %d.%m.%Y')} | "
                              f"Сделал: {interaction.user.name} | "
                              f"Время до окончания {time_end.strftime('%H:%M %d.%m.%Y')}")

        message = await interaction.channel.send(embed=embed)  # noqa
        message_id = message.id

        for i in range(1, len(answers) + 1):
            await message.add_reaction(f"{i}\N{combining enclosing keycap}")

        poll_time = {
            "poll_is_on": True,
            "poll_data": {
                "emoji": "✅",
                "message": message.id,
                "voices": {}
            }
        }

        with open("static/poll_file.json", "w", encoding='utf8') as poll_file:
            js.dump(poll_time, poll_file, indent=3)

        await asyncio.sleep(int(self.time_on_poll.value) * 60)

        try:
            poll_time = {
                "poll_is_on": False,
                "poll_data": {}
            }
            message = await interaction.channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.send(embed=await bot.embed("Сообщение с голосование не было найдено.",
                                                         "Произошла ошибка и сообщение с голосование не "
                                                         "было найдено."))
            with open("static/poll_file.json", "w", encoding='utf8') as poll_file:
                js.dump(poll_time, poll_file, indent=4)
            return
        else:
            with open("static/poll_file.json", "w", encoding='utf8') as poll_file:
                js.dump(poll_time, poll_file, indent=4)

        embed = message.embeds[0].to_dict()

        now = datetime.now() - timedelta(hours=self.td)

        del embed['description']
        embed['author']['name'] = f"Результаты. {embed['author']['name'][0].title()}{embed['author']['name'][1::]}"
        embed['footer'][
            'text'] = f"Голосование завершено в {now.strftime('%H:%M %d.%m.%Y')} | Создал {ineraction.user.name}"

        await message.edit(embed=discord.Embed.from_dict(embed))

        try:
            os.remove("static/poll_file.json")
        except Exception as error:
            bot.log.error(error)

    # Дурацкая фигня
    # https://discord.com/channels/336642139381301249/381965515721146390/1064789246042456124
    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        interaction.client.log.error(error)
        await interaction.channel.send(f"Произошло непредвиденное исключение!\nОшибка — `{error}`")


class Admin(AbstractCog, name="Админ-команды"):
    async def get_tech_channel(self, guild_id):
        guild_discord = GuildDiscord \
            .select(GuildDiscord.tech_channel) \
            .where(GuildDiscord.guild == guild_id)

        tech_channel = db.execute(guild_discord)

        if guild_discord.exists():
            channel = await self.client.fetch_channel(tech_channel.fetchone()[0])
            return channel
        else:
            # self.client.log.warning("Channel for logging not found. Pass message.")
            return

    @app_commands.command(name='logging',
                          description="Устанавливает канал для логирования")
    @app_commands.describe(channel="Канал для логирования")
    @app_commands.default_permissions(manage_channels=True, manage_guild=True)
    @app_commands.checks.cooldown(1, 30, key=lambda interaction: interaction.user.id)
    @app_commands.guild_only()
    @app_commands.check(AbstractCog.reconnect)
    async def add_tech_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        ctx: Context = await self.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        GuildDiscord.update({GuildDiscord.tech_channel: channel.id}).where(GuildDiscord.guild == ctx.guild.id).execute()
        await message.edit(embed=await ctx.embed_message(f"Канал «{channel.name}» успешно назначен.",
                                                         f"Канал {channel.mention} успешно назначен в качестве канала "
                                                         f"для получения различной информации."))

    @app_commands.command(name='rp_request',
                          description="Устанавливает канал для заявок на РП-Сессию")
    @app_commands.describe(channel="Канал для заявок")
    @app_commands.default_permissions(manage_channels=True, manage_guild=True)
    @app_commands.checks.cooldown(1, 30, key=lambda interaction: interaction.user.id)
    @app_commands.guild_only()
    @app_commands.check(AbstractCog.reconnect)
    async def add_tech_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        bot: Katherine = interaction.client  # noqa

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        GuildDiscord.update({GuildDiscord.rp_request_channel: channel.id})\
            .where(GuildDiscord.guild == interaction.guild.id).execute()

        await message.edit(embed=await bot.embed(f"Канал «{channel.name}» успешно назначен.",
                                                 f"Канал {channel.mention} успешно назначен в качестве канала "
                                                 f"для записей на РП-Сессии."))

    @app_commands.command(description="Перезапускает бота")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 300, key=lambda interaction: interaction.guild.id)
    async def restart(self, interaction: discord.Interaction):
        await interaction.response.send_message("Бот уходит на перезагрузку. "
                                                "Восстановление работы ожидается в течении 10-60 секунд.")
        exit()

    @app_commands.command(name="удалить",
                          description="Удаляет большое кол-во сообщений, сохраняя в файл")
    @app_commands.describe(count="Число сообщений для удаления (не больше 100)")
    @app_commands.checks.cooldown(1, 15, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(manage_messages=True, manage_channels=True)
    @app_commands.check(AbstractCog.reconnect)
    async def purge(self, interaction: discord.Interaction, count: int):
        ctx: Context = await self.client.get_context(interaction)
        await ctx.supplement()

        if count > 100 or count < 0:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Превышено/Занижено число удаляемых сообщений.",
                                              "Нельзя удалять <1/>100 сообщений!"),
                ephemeral=True)
            return

        await interaction.response.defer()

        messages = [message async for message in ctx.channel.history(limit=count + 1)]
        messages = reversed(messages)

        with open("static/buff/purge.txt", "w", encoding='utf8') as backup_file:
            backup_file.write("Deleted messages:\n\n")
            for msg in messages:
                backup_file.write(
                    "\n" + str(msg.author.name) + "#" + str(msg.author.discriminator) + " (" + str(
                        msg.created_at) + "): " + msg.content)

        backup_file = open("static/buff/purge.txt", "rb")
        msgs_deleted = discord.File(backup_file, filename="purge_messages.txt")

        await interaction.channel.purge(limit=count + 1)

        await ctx.log_to_channel(
            embed=await ctx.embed_message(f"{interaction.user.name} удалил {count} шт. сообщений",
                                          f"{interaction.user.mention} воспользовался командой для массового удаления "
                                          f"сообщений и удалил сообщения в количестве {count} шт.",
                                          icon_url=interaction.user.avatar.url,
                                          thumbnail="http://cdn.onlinewebfonts.com/svg/img_229056.png"),  # noqa
            file=msgs_deleted)

        file.close()
        backup_file.close()
        msgs_deleted.close()

        os.remove("static/buff/purge.txt")

        await interaction.channel.send(content=f"***Успешно удалено {count} сообщений(-ие)!***", delete_after=5.0)

    @app_commands.command(name="голосование",
                          description="Организует голосование на определенное время")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 15, key=lambda interaction: interaction.user.id)
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True, manage_channels=True)
    async def polls_time(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModalChoiceTime())

    @commands.Cog.listener()
    @commands.check(AbstractCog.reconnect)
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.id == self.client.user.id:
            return

        with open("static/poll_file.json", "r", encoding='utf8') as poll_file:
            previously = js.load(poll_file)

        if payload.message_id != previously['poll_data']['message']:
            return

        user = payload.member
        try:
            channel: discord.TextChannel = user.guild.get_channel(payload.channel_id)
            message: discord.Message = await channel.fetch_message(payload.message_id)
        except discord.NotFound as error:
            self.client.log.error(error)
            return None

        try:
            if str(user.id) not in previously['poll_data']['voices'].keys():
                embed = message.embeds[0].to_dict()
                embed["fields"][0]['value'] += f" {payload.emoji}"
                await message.edit(embed=discord.Embed.from_dict(embed))
                await message.remove_reaction(payload.emoji, user)
                previously['voices'][user.id] = int(1)
            else:
                await message.remove_reaction(payload.emoji, user)
        except Exception as error:
            print(error)

        with open("static/poll_file.json", "w", encoding='utf8') as poll_file:
            js.dump(previously, poll_file, indent=3)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: Context, guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}")
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(client):
    await client.add_cog(Admin(client))
