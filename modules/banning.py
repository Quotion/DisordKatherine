import traceback

import discord
import datetime
import steam.steamid

from utils.models import *
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from main import Katherine, AbstractCog
from utils.context import Context


class Ban(AbstractCog, name="Система банов"):
    def __init__(self, *args, **kwargs):
        super(Ban, self).__init__(*args, **kwargs)
        self.servers = 2

    async def __connect__(self):  # noqa
        try:
            db.connect(reuse_if_open=True)
            return True
        except peewee.OperationalError:
            # logger.error("Connect to DB failed. Retry in 2 sec.")
            return False

    async def ban_message(self, data_gamer):  # noqa
        embed = discord.Embed(
            colour=discord.Colour.red()
        )
        embed.set_author(name=f'Информация по бану игрока с ником {data_gamer.SID.nick}')
        embed.add_field(name='SteamID:',
                        value=data_gamer.SID_id, inline=False)
        embed.add_field(name='Номер сервера: ',
                        value=data_gamer.server, inline=False)
        embed.add_field(name='Точная дата бана: ',
                        value=time.ctime(int(data_gamer.ban_date)), inline=True)
        embed.add_field(name='Дата разбана: ',  # noqa
                        value='Примерно через ∞ мин.' if data_gamer.unban_date == 0 else time.ctime(
                            int(data_gamer.unban_date)), inline=False)
        embed.add_field(name='Причина бана: ',
                        value=data_gamer.ban_reason, inline=False)
        embed.add_field(name='Администратор, выписавший бан: ',
                        value=data_gamer.ban_admin, inline=False)
        return embed

    async def check_ban(self, ban, client):  # noqa
        embed = discord.Embed(
            colour=discord.Colour.red()
        )
        embed.set_author(name=f'Информация по бану игрока с ником {client.name}')
        embed.add_field(name='Ник забаненого:',
                        value=client.name, inline=False)
        embed.add_field(name='Дата разбана: ',
                        value='Примерно через ∞ мин.' if ban.unban_date == 0 else time.ctime(int(ban.unban_date)),
                        inline=False)
        embed.add_field(name='Время, через сколько бан окончится: ',
                        value=f'{(int(time.time()) - ban.unban_date) // 60} мин.', inline=False)
        embed.add_field(name='Причина бана: ',
                        value=ban.reason, inline=False)
        embed.add_field(name='Администратор, выписавший бан: ',
                        value=ban.ban_admin, inline=False)
        return embed

    async def discord_check_ban(self, data_gamer):  # noqa
        embed = discord.Embed(
            colour=discord.Colour.red()
        )
        embed.set_author(name=f'Информация по бану игрока {data_gamer.SID.nick}')
        embed.add_field(name='Точная дата бана: ',
                        value=time.ctime(int(data_gamer.ban_date)), inline=False)
        embed.add_field(name='Дата разбана: ',
                        value='Примерно через ∞ мин.' if data_gamer.unban_date == 0 else time.ctime(
                            int(data_gamer.unban_date)), inline=False)
        embed.add_field(name='Причина бана: ',
                        value=data_gamer.ban_reason, inline=False)
        embed.add_field(name='Администратор, выписавший бан: ',
                        value=data_gamer.ban_admin, inline=False)
        return embed

    @commands.check(AbstractCog.reconnect)
    async def check_client(self, ctx, client):
        if str(client).find("<@") != -1:
            client = await commands.MemberConverter().convert(ctx, client)

            if not client:
                await ctx.send(
                    embed=await ctx.embed_message("Discord пользователя не был найден.",
                                                  "Пользователь с таким Discord-ом не был найден. Пожалуйста "
                                                  "перепроверьте правильность введенных Вами данных."))
                return None
            else:
                return client
        else:
            client = client.upper()
            try:
                GmodPlayer.get(GmodPlayer.SID == client)
            except peewee.DoesNotExist:
                # logger.debug("SteamID for ban not in BD.")
                await ctx.send(
                    embed=await ctx.embed_message("SteamID не найдено в базе данных.",
                                                  "Игрок с таким SteamID ни разу не появлялся на сервере и не был "
                                                  "внесен в базу данных, поэтому забанить его можно только после "
                                                  "его появления на сервере."))
                return None
            else:
                return client

    @commands.check(AbstractCog.reconnect)
    async def get_data_gamer(self, ctx, client):
        SID = client

        if isinstance(client, discord.Member):
            try:
                user = UserDiscord.get(UserDiscord.discord_id == client.id)
            except peewee.DoesNotExist:
                await ctx.channel.send(embed=await ctx.embed_message("У данного пользователя нету профиля",
                                                                     "Вы не сможете забанить данного игрока"
                                                                     "через Discord, т.к. у него нету"
                                                                     "профиля."))
                return None

            if not user.SID:
                await ctx.channel.send(embed=await ctx.embed_message("Игрок не синхронизирован",
                                                                     "Игрок с таким Discord-ом не "
                                                                     "синхронизирован. Введите его SteamID, "
                                                                     "чтобы забанить."))
                return None

            SID = user.SID

        try:
            data_gamer = GmodBan.get(GmodBan.SID == SID)
        except Exception as error:  # noqa
            # logger.error(error)
            await ctx.channel.send(embed=await ctx.embed_message("Игрок ни разу не был на сервере",
                                                                 "Игрок с таким Discord-ом не "
                                                                 "был найден в БД сервера."))
            return None

        return data_gamer

    @app_commands.command(name='бан',
                          description="Банит игрока")
    @app_commands.describe(client="SteamID или Discord, кого необходимо забанить",
                           ban_time="Время в минутах")
    @app_commands.checks.cooldown(1, 15, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(administrator=True)
    @app_commands.check(AbstractCog.reconnect)
    async def ban(self, interaction: discord.Interaction, client: str, ban_time: int, *, reason: str):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        discord_client = await self.check_client(ctx, client)

        if not discord_client:
            return

        time_ban = int(datetime.today().timestamp())
        time_unban = int(ban_time) * 60 + int(datetime.today().timestamp())

        data_gamer = await self.get_data_gamer(ctx, discord_client)
        print(data_gamer)

        if not data_gamer:
            return

        for column in data_gamer:
            if column.ban == 0 and column.ban_admin == '':
                column.ban_reason = reason
                column.ban_admin = ctx.author.name
                column.ban_date = time_ban
                column.unban_date = time_unban
                column.save()
                await ctx.channel.send(embed=await self.ban_message(column))
            else:
                await message.edit(
                    content=None,
                    embed=await ctx.embed_message("Игрок уже забанен на {} сервере.".format(column.server),
                                                  "Игрок **{}({})** уже забанен по причине `"
                                                  "{}`".format(column.SID.nick,
                                                               column.SID_id,
                                                               column.ban_reason)))

    @app_commands.command(name='разбан',
                          description="Разбанивает пользователя")
    @app_commands.describe(client="SteamID или Discord пользователя, которого необходимо разбанить")
    @app_commands.checks.cooldown(1, 30, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(administrator=True)
    @app_commands.check(AbstractCog.reconnect)
    async def unban(self, interaction: discord.Interaction, client: str):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        now = datetime.now()

        client = await self.check_client(ctx, client)

        if not client:
            return

        data_gamer = await self.get_data_gamer(ctx, client)

        if not data_gamer:
            return

        for column in data_gamer:
            if column.ban > 0 and column.ban_reason != '':
                column.ban_reason = None
                column.ban_admin = None
                column.ban_date = None
                column.unban_date = None
                column.save()
                await ctx.channel.send(embed=await ctx.embed_message(
                    f"{data_gamer.SID.nick} был разбанен на {column.server} сервере.",
                    f"Игрок **{data_gamer.SID.nick}"
                    f"({data_gamer.SID_id}**) разбанен.\n"
                    f"Дата разбана: "
                    f"({now.strftime('%H:%M %d.%m.%Y')})\n"
                    f"Разбанил: {ctx.author.mention}", ))
            else:
                await message.edit(
                    content=None,
                    embed=await ctx.embed_message(f"Игрок уже забанен на {column.server} сервере.",
                                                  f"Игрок **{column.SID.nick}({column.SID_id})** уже забанен по "
                                                  f"причине `{column.ban_reason}`"))

    @app_commands.command(name='проверь',
                          description="Проверяет, забанен ли человек или нет")
    @app_commands.describe(client="Discord или SteamID пользователя")
    @app_commands.checks.cooldown(1, 30, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(administrator=True)
    @commands.check(AbstractCog.reconnect)
    async def check_ban(self, interaction: discord.Interaction, client: str):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        client = await self.check_client(ctx, client)

        if not client:
            return

        data_gamer = await self.get_data_gamer(ctx, client)

        if not data_gamer:
            return

        user = data_gamer[0]

        if user.ban == 0 and (not user.ban_admin or user.ban_admin == "None"):
            await message.edit(content=None,
                               embed=await ctx.embed_message("Игрок не забнен",
                                                             f"Игрок (**{user.SID_id}**) не забанен."))
        else:
            await message.edit(content=None,
                               embed=await self.discord_check_ban(user))

    @app_commands.command(name='синхр',
                          description="Синхронизирует аккаунт Discord и Garry's mod-а")
    @app_commands.describe(arg="Ссылка на Steam или SteamID")
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.user.id)
    @app_commands.check(AbstractCog.reconnect)
    async def sync(self, interaction: discord.Interaction, arg: str):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        try:
            user = UserDiscord.get(UserDiscord.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await message.edit(
                content=None,
                embed=await ctx.embed_message("Создайте профиль для синхронизации!",
                                              f"Для того чтобы синхронизировать свой аккаунт в Garry's mod и Discord "
                                              f"необходимо создать **профиль**. Для этого введите команду "
                                              f"**/профиль**"))
            return

        if arg.startswith('https://steamcommunity.com/') or arg.startswith('http://steamcommunity.com/'):
            SteamID = steam.steamid.steam64_from_url(arg)
            if not SteamID:
                await message.edit(
                    content=None,
                    embed=await ctx.embed_message("SteamID не найден.",
                                                  f"После отправки запроса с данными, которые Вы ввели, нам не пришло "
                                                  f"подтверждения, что такой SteamID существует."))
                return
            steamid = steam.steamid.SteamID(SteamID).as_steam2_zero
        else:
            SteamID = steam.steamid.SteamID(arg)
            if not SteamID:
                await message.edit(
                    content=None,
                    embed=await ctx.embed_message("SteamID не найден.",
                                                  f"После отправки запроса с данными, которые Вы ввели, нам не пришло "
                                                  f"подтверждения, что такой SteamID существует."))
                return
            steamid = SteamID.as_steam2_zero

        try:
            player = GmodPlayer.get(GmodPlayer.SID == steamid)
        except peewee.DoesNotExist:
            await message.edit(
                content=None,
                embed=await ctx.embed_message("Не найден в базе данных.",
                                              f"Игрок с таким SteamID ни разу не играл на сервере."))
            return

        if user.SID is None or user.SID == "None":
            user.SID = steamid
            user.save()
            await interaction.response.send_message(
                embed=await ctx.embed_message("SteamID успешно синхронизирован.",
                                              f"Спасибо за синхронизацию вашего аккаунта Garry's mod и Discord."))
        elif player.SID == user.SID:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Вы уже синхронизированы.",
                                              f"Данный SteamID уже принадлежит вашему аккаунту."))
        else:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Данный SteamID уже используется.",
                                              f"Пожалуйста не пытайтесь ввести чужой SteamID. "
                                              f"Это ни к чему хорошему не приведет."))

    @app_commands.command(name='разсинхр',
                          description="Команда, с помощью которой, можно разсинхронизировать "
                                      "аккаунт в Garry's mod и Discord")
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.user.id)
    @app_commands.check(AbstractCog.reconnect)
    async def sync_down(self, interaction: discord.Interaction):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        try:
            user = UserDiscord.get(UserDiscord.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Создайте профиль для синхронизации!",
                                              f"Для того чтобы синхронизировать свой аккаунт в Garry's mod и Discord "
                                              f"необходимо создать **профиль**. Для этого введите команду "
                                              f"**/профиль**"))
            return

        if user.SID is None or user.SID == "None":
            await interaction.response.send_message(
                embed=await ctx.embed_message("Вы не были синхронизированы.",
                                              f"Чтобы разсинхронизировать ваш аккаунт со Garry's mod-ом вам нужно для "
                                              f"начало его синхронизировать."))
        else:
            user.SID = None
            user.save()
            await interaction.response.send_message(
                embed=await ctx.embed_message("Аккаунт успешно разсинхронизирован.",
                                              f"Ваш аккаунт Garry's mod-а успешно разсинхронизирован с Discord"))

    @app_commands.command(name="ранг",
                          description="Изменяет ранг человека на NoRank-серверах")
    @app_commands.describe(client="SteamID или Discord пользователя",
                           rank="Ранг пользователя")
    @app_commands.choices(rank=[
        app_commands.Choice(name='Машинист электропоезда', value="user"),
        app_commands.Choice(name='Модератор', value='operator'),
        app_commands.Choice(name='Администратор', value='superadmin')
    ])
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(administrator=True)
    @commands.check(AbstractCog.reconnect)
    async def set_rank(self, interaction: discord.Interaction, client: str, rank: app_commands.Choice[str]):
        ctx: Context = await interaction.client.get_context(interaction)  # noqa
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        client = await self.check_client(ctx, client)

        if not client:
            return

        data_gamer = await self.get_data_gamer(ctx, client)

        if not data_gamer:
            return

        data_gamer.SID.group = rank.value
        data_gamer.SID.save()
        # logger.info("User with SteamID {} successfully changed rank.".format(data_gamer.SID))
        await message.edit(content=None,
                           embed=await ctx.embed_message("Ранг игрока был изменен.",
                                                         f"Ранг игрока **{data_gamer.SID.nick}** был изменен на "
                                                         f"{rank.name}."))


async def setup(client):
    await client.add_cog(Ban(client))
