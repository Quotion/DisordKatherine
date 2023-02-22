# https://github.com/Quotion/ProjectKate
import asyncio

import discord
import logging
import logging.config
import peewee
import os
import io

from modules import rpsession
from utils.context import Context

from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Union, Any

from utils.models import (GuildDiscord, GmodPlayer, GmodBan, Rating, Dynamic, UserDiscord, RoleDiscord, RoleUser,
                          Promocode, StatusGMS, DonateUser, Group, PlayerGroupTime, RecordsToRP, RPSession, db)


class Katherine(commands.Bot):
    ctx: Context

    def __init__(self, logger):  # noqa
        super(Katherine, self).__init__(
            command_prefix='к!',
            intents=discord.Intents.all()
        )

        logger.info("Katherina start init...")
        self.__logger = logger

        try:
            db.connect(reuse_if_open=True)
            db.create_tables([GuildDiscord, GmodPlayer, GmodBan, Rating, Dynamic,
                              UserDiscord, RoleDiscord, RoleUser, Promocode,
                              StatusGMS, DonateUser, Group, PlayerGroupTime,
                              RecordsToRP, RPSession])
        except peewee.OperationalError:
            logger.critical("Database unreachable...")
            exit()

    @staticmethod
    async def reconnect(ctx):
        try:
            db.connect()
        except peewee.OperationalError:
            db.close()
            db.connect()
        except:
            return False
        finally:
            return True

    @property
    def log(self):
        return self.__logger

    async def embed(self, *args, **kwargs):
        return await self.ctx.embed_message(*args, **kwargs)

    async def get_context(self, origin: Union[discord.Interaction, discord.Message], /, *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def member_action(self, member: discord.Member, is_join: bool = True):
        now = datetime.now()
        embed = discord.Embed(colour=discord.Colour.green() if is_join else discord.Colour.dark_red(),
                              title=f"Пользователь {'ПРИСОЕДИНИЛСЯ к серверу' if is_join else 'ПОКИНУЛ сервер'} "
                                    f"«{member.guild.name}»",
                              timestamp=now)

        embed.set_author(name=self.user.name, icon_url=self.user.avatar)
        embed.add_field(name="Информация о пользователе: ",
                        value=f"Discord: {member.mention}\n"
                              f"DiscordTag: `{member.name}#{member.discriminator}`\n"
                              f"DiscordID: `{member.id}`",
                        inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=member.guild.name, icon_url=member.guild.icon)
        return embed

    async def message_edit(self, before, after) -> discord.Embed:
        now = datetime.now()
        embed = discord.Embed(colour=discord.Colour.from_rgb(255, 191, 131),
                              title="РЕДАКТИРОВАНО сообщение", timestamp=now)

        content_before: str = before.content
        content_after: str = after.content
        big_message: bool = False

        if len(before.content) > 100:
            content_before = before.content[0:100] + "..."
            big_message = True
        if len(after.content) > 100:
            content_after = after.content[0:100] + "..."
            big_message = True

        if big_message:
            with io.open("changelog.txt", "w", encoding='utf8') as write_file:
                write_file.write(f"Сообщение до: {before.content}"
                                 f"\n\n"
                                 f"Сообщение после: {after.content}")

        embed.set_author(name=self.user.name, icon_url=self.user.avatar)
        embed.add_field(name="Пользователь", value=after.author.mention)
        embed.add_field(name="Канал", value=after.channel.mention)
        embed.add_field(name="Время", value=f"<t:{int(now.timestamp())}:f>")
        embed.add_field(name="Сообщение ПЕРЕД и ПОСЛЕ редактирования:",
                        value=f"**Перед**: {content_before}\n**После**: {content_after}",
                        inline=False)
        embed.set_thumbnail(url=before.author.avatar)
        embed.set_footer(text=before.guild.name, icon_url=before.guild.icon)

        return embed

    async def delete_message(self, message: discord.Message, content: str):
        now = datetime.now()
        embed = discord.Embed(colour=discord.Colour.from_rgb(209, 67, 67),
                              title="УДАЛЕНО сообщение", timestamp=now)

        embed.set_author(name=self.user.name, icon_url=self.user.avatar)
        embed.add_field(name="Текст сообщения:", value=content, inline=False)
        embed.add_field(name="Пользователь", value=message.author.mention)
        embed.add_field(name="Канал", value=message.channel.mention)
        embed.add_field(name="Время", value=f"<t:{int(now.timestamp())}:f>")
        embed.set_thumbnail(url=message.author.avatar)
        embed.set_footer(text=message.guild.name, icon_url=message.guild.icon)

        return embed

    async def roles_changes(self, before, after):
        now = datetime.now()
        embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 63),
                              title="ИЗМЕНЕНИЕ ролей", timestamp=now)

        embed.set_author(name=self.user.name, icon_url=self.user.avatar)
        embed.add_field(name="До ИЗМЕНЕНИЯ",
                        value=' '.join([role.mention for role in before.roles]),
                        inline=False)
        embed.add_field(name="После ИЗМЕНЕНИЯ:",
                        value=' '.join([role.mention for role in after.roles]),
                        inline=False)
        embed.set_footer(text=before.guild.name, icon_url=before.guild.icon)
        embed.set_thumbnail(url=before.display_avatar.url)

        return embed

    @commands.check(reconnect)
    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name="{}help".format(self.command_prefix[0])))

        self.add_view(rpsession.RPSessionButtonsView())
        self.add_view(rpsession.ButtonViewOrganizerOfRPSession())
        self.add_view(rpsession.ButtonViewForRecordRPSession())

        guilds = GuildDiscord.select(GuildDiscord.guild_id, GuildDiscord.guild)
        for guild_discord in guilds:
            guild = self.get_guild(guild_discord.guild)
            for role in guild.roles:
                RoleDiscord.insert(role_id=role.id, guild_id=guild_discord.guild_id).on_conflict_ignore().execute()

        for guild in self.guilds:
            try:
                message: discord.Message = await guild.system_channel.send("Init. Please wait.")
                await message.delete()
            except discord.Forbidden:
                for channel in guild.channels:
                    member: discord.Member = guild.get_member(self.user.id)
                    if discord.Permissions.send_messages in channel.permissions_for(member):
                        message: discord.Message = await guild.system_channel.send("Init. Please wait.")
                        await message.delete()

        self.log.info('Bot {} now loaded for 100%.'.format(self.user.name))

    async def on_guild_join(self, guild: discord.Guild):
        GuildDiscord.insert(guild=guild.id).on_conflict_ignore().execute()
        self.log.info('Someone added {} to guild "{}"'.format(self.user.name, guild.name))

    @commands.check(reconnect)
    async def on_command_error(self, ctx: Context, exception: Exception, /) -> None:
        self.log.error(exception)

    # async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
    #     self.log.error(f"Event: {event_method}\nArgs: {args}\nKwargs: {kwargs}")

    @commands.check(reconnect)
    async def on_member_join(self, member: discord.Member):
        roles_higher = list()

        UserDiscord.insert(discord_id=member.id).on_conflict_ignore().execute()
        guild: GuildDiscord = GuildDiscord.get(GuildDiscord.guild == member.guild.id)
        query = RoleUser \
            .select(RoleUser, UserDiscord, RoleDiscord) \
            .join(RoleDiscord) \
            .switch(RoleUser) \
            .join(UserDiscord) \
            .where(UserDiscord.discord_id == member.id)

        if not query.exists() and guild.guild == member.guild.id:
            join_role = member.guild.get_role(guild.default_role)
            await member.add_roles(join_role)

        for signature in query:
            role = member.guild.get_role(signature.rolediscord.role_id)
            if role.name == "@everyone":
                continue
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                roles_higher.append(role)

        await self.ctx.log_to_channel(embed=await self.member_action(member))

        if len(roles_higher) == 0:
            return

        embed = discord.Embed(colour=discord.Colour.red())
        if len(roles_higher) == 1:
            embed.set_author(name="Недостаточно прав, для выдачи роли")
            embed.description = f"{roles_higher[0].name} не может быть выдана пользователю {member.mention}, т.к. у " \
                                f"бота недостаточно прав для этого."
            self.log.debug(f"Role can't be add to {member.name}#{member.discriminator}. Forbidden.")
        else:
            embed.set_author(name="Недостаточно прав, для выдачи ролей")
            embed.description = f"Роли не могут быть выданы пользователю {member.mention} из-за недостаточных прав " \
                                f"у бота. Список:\n{', '.join(role.name for role in roles_higher)}\n"
            self.log.debug(f"Roles can't be add to {member.name}#{member.discriminator}. Forbidden.")

        await self.ctx.log_to_channel(embed=embed)
        self.log.info(f"{member.name} enter in {member.guild.name}")

    @commands.check(reconnect)
    async def on_member_remove(self, member):
        if member.bot:
            return

        try:
            user = UserDiscord.get(UserDiscord.discord_id == member.id)
        except peewee.DoesNotExist:
            self.log.debug("User does not exists.")
            return

        try:
            RoleUser.delete().where(RoleUser.userdiscord_id == user.id).execute()
        except peewee.DoesNotExist:
            pass

        for role in member.roles:
            if role.name == "@everyone":
                continue

            role = RoleDiscord.get(RoleDiscord.role_id == role.id)

            try:
                user.user_role.add(role)
            except peewee.PeeweeException as error:
                self.log.error(error)

        await self.ctx.log_to_channel(embed=await self.member_action(member, is_join=False))
        self.log.info("Member remove from guild ({})".format(member.guild.name))

    async def on_message_edit(self, msg_before, msg_after):
        if msg_after.content == msg_before.content or msg_before.author.bot:
            return

        embed = await self.message_edit(msg_before, msg_after)

        try:
            plot = io.open("static/buff/changelog.txt", "rb")
        except FileNotFoundError:
            pass
            await self.ctx.log_to_channel(embed=embed)
        except Exception as error:
            logging.error(error)
        else:
            msg_changes = discord.File(plot, filename="message_changes.txt")
            await self.ctx.log_to_channel(embed=embed, file=msg_changes)
            plot.close()
            os.remove("static/buff/changelog.txt")
            msg_changes.close()

    @commands.check(reconnect)
    async def on_message_delete(self, message, check=None, content=None):
        if message.author.bot:
            return

        if message.content:
            if len(message.content) > 50:
                content = message.content[0:40] + "..."
                check = True

            if check:
                try:
                    with io.open("static/buff/message_deleted.txt", "w", encoding='utf8') as open_file:
                        open_file.write("Deleted message:\n" + message.content)

                    delete_message = io.open("static/buff/message_deleted.txt", "rb")
                    msg_delete = discord.File(delete_message, filename="message_deleted.txt")

                    await self.ctx.log_to_channel(embed=await self.delete_message(message, content),
                                                  file=msg_delete)

                    delete_message.close()
                    msg_delete.close()
                    os.remove("static/buff/message_deleted.txt")
                except Exception as error:
                    logging.error(error)
            else:
                await self.ctx.log_to_channel(embed=await self.delete_message(message, message.content))
        elif not message.content:
            await self.ctx.log_to_channel(embed=await self.delete_message(message, "`Пустое сообщение`"))
        else:
            self.log.debug("Channel for logging not found. Pass message.")
            return

    @commands.check(reconnect)
    async def on_member_update(self, before_member: discord.Member, after_member: discord.Member):
        if before_member.roles != after_member.roles:
            await self.ctx.log_to_channel(embed=await self.roles_changes(before_member, after_member))

    @commands.check(reconnect)
    async def on_raw_reaction_add(self, payload):
        if payload.member.id == self.user.id:
            return

        guild = payload.member.guild
        role = guild.get_role(699898326698688542)

        if payload.message_id == 768536526207844372 and payload.emoji.name == "✅":
            try:
                await payload.member.add_roles(role)
            except discord.Forbidden as error:
                self.log.error(error)

    @commands.check(reconnect)
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.user.id:
            return

        guild = self.get_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        role = guild.get_role(699898326698688542)
        if payload.message_id == 768536526207844372 and payload.emoji.name == "✅":
            try:
                await member.remove_roles(role)
            except discord.Forbidden as error:
                self.log.error(error)

    @commands.check(reconnect)
    async def on_message(self, message: discord.Message) -> None:
        if isinstance(message.channel, discord.DMChannel):
            return

        self.ctx: Context = await self.get_context(message)  # noqa
        await self.ctx.supplement()

        await self.process_commands(message)


class AbstractCog(commands.Cog):
    def __init__(self, client: Katherine):
        self.client: Katherine = client
        self.client.tree.on_error = self.cog_app_command_error

    async def cog_load(self) -> None:
        self.client.log.info(f"Cog {self.__class__.__name__} loaded!")

    @staticmethod
    async def reconnect(ctx):
        try:
            db.connect()
        except peewee.OperationalError:
            db.close()
            db.connect()
        except:
            return False
        finally:
            return True

    async def cog_command_error(self, ctx: Context, error: Exception) -> None:
        now = datetime.now()

        if isinstance(error, commands.NoPrivateMessage):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.red())
            embed.set_author(name="Недостаточно прав.")
            embed.description = "У вас недостаточно прав для использования данной команды."
            embed.timestamp = now
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Нехватка аргументов в команде.")
            embed.description = f"{ctx.author.mention} недостаточно аргументов в команде, которую вы используете."
            embed.set_footer(text="Ниже представлена дополнительная информация")
            embed.timestamp = now
            await ctx.send(embed=embed)
            await ctx.send_help(ctx.command)
        elif isinstance(error, commands.NoPrivateMessage):
            self.client.log.debug(error)  # noqa
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Эта команда может быть использована только на сервере.")
            embed.description = f"{ctx.author.mention}, команда **{ctx.message.content.split()[0]}** не может быть " \
                                f"использована в `Личных Сообщениях`."
            embed.timestamp = now
            await ctx.send(embed=embed)
        elif isinstance(error, commands.TooManyArguments):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Слишком много аргументов в команде.")
            embed.description = f"{ctx.author.mention} вы ввели аргументы, которые скорее всего не нужны здесь."
            embed.set_footer(text="Ниже представлена дополнительная информация")
            embed.timestamp = now
            await ctx.send(embed=embed)
            await ctx.send_help(ctx.command)
        elif isinstance(error, commands.CommandNotFound):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.red())
            embed.set_author(name="Команда не найдена.")
            embed.description = f"Команда **{ctx.message.content.split()[0]}** не существует или вы ошиблись в ее " \
                                f"написании."
            embed.timestamp = now
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandOnCooldown):
            self.client.log.debug(error)  # noqa
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Пожалуйста, не спешите.")
            if int(error.retry_after) == 1:
                cooldown = "{}, ожидайте ещё {} секунду перед тем как повторить команду."
            elif 2 <= int(error.retry_after) <= 4:
                cooldown = "{}, ожидайте ещё {} секунды перед тем как повторить команду."
            else:
                cooldown = "{}, ожидайте ещё {} секунд перед тем как повторить команду."
            embed.description = cooldown.format(ctx.author.mention, int(error.retry_after))
            embed.timestamp = now
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BadArgument):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.red())
            embed.set_author(name="Аргументы не соответствует нужным типам.")
            embed.description = f"Похоже, что тип данных, который вы ввели в качестве аргумента не соответствует " \
                                f"нужному. Доп. информация:\n **{error}**"
            embed.timestamp = now
            await ctx.send(embed=embed)
            await ctx.send_help(ctx.command)
        else:
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.dark_red())
            embed.set_author(name="Произошло непредвиденное исключение.")
            embed.description = str(error)
            embed.timestamp = now
            await ctx.send(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: Exception) -> None:
        now = datetime.now()

        if isinstance(error, app_commands.MissingPermissions):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.red())
            embed.set_author(name="Недостаточно прав.")
            embed.description = "У вас недостаточно прав для использования данной команды."
            embed.timestamp = now
            if interaction.response.is_done():
                await interaction.channel.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
        elif isinstance(error, app_commands.NoPrivateMessage):
            self.client.log.debug(error)  # noqa
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Эта команда может быть использована только на сервере.")
            embed.description = f"{interaction.user.mention}, команда **{interaction.message.content.split()[0]}** " \
                                f"не может быть использована в `Личных Сообщениях`."
            embed.timestamp = now
            if interaction.response.is_done():
                await interaction.channel.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
        elif isinstance(error, app_commands.CommandNotFound):
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.red())
            embed.set_author(name="Команда не найдена.")
            embed.description = f"Команда **{interaction.message.content.split()[0]}** " \
                                f"не существует или вы ошиблись в ее написании."
            embed.timestamp = now
            if interaction.response.is_done():
                await interaction.channel.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
        elif isinstance(error, app_commands.CommandOnCooldown):
            self.client.log.debug(error)  # noqa
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.set_author(name="Пожалуйста, не спешите.")
            if int(error.retry_after) == 1:
                cooldown = "{}, ожидайте ещё {} секунду перед тем как повторить команду."
            elif 2 <= int(error.retry_after) <= 4:
                cooldown = "{}, ожидайте ещё {} секунды перед тем как повторить команду."
            else:
                cooldown = "{}, ожидайте ещё {} секунд перед тем как повторить команду."
            embed.description = cooldown.format(interaction.user.mention, int(error.retry_after))
            embed.timestamp = now
            if interaction.response.is_done():
                await interaction.channel.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
        else:
            self.client.log.debug(error)
            embed = discord.Embed(colour=discord.Colour.dark_red())
            embed.set_author(name="Произошло непредвиденное исключение.")
            embed.description = str(error)
            embed.timestamp = now
            if interaction.response.is_done():
                await interaction.channel.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)


async def main():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    logging.getLogger('discord.http').setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename='logs/discord.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )

    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    discord.utils.setup_logging(level=logging.INFO)
    client = Katherine(logger)

    await client.load_extension("modules.commands")
    await client.load_extension("modules.banning")
    await client.load_extension("modules.admin")
    await client.load_extension("modules.rpsession")

    await client.start(os.environ.get('KATHERINE'))


if __name__ == "__main__":
    asyncio.run(main())
