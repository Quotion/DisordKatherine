import discord
import peewee

from discord import app_commands

from datetime import datetime
from typing import Any, Optional, Union

from main import Katherine, AbstractCog
from utils.models import RPSession, RecordsToRP, UserDiscord, Fortune


class ButtonViewOrganizerOfRPSession(discord.ui.View):
    def __init__(self):
        super(ButtonViewOrganizerOfRPSession, self).__init__(timeout=None)

    def get_user_record(self, interaction: discord.Interaction) -> Optional[Union[RecordsToRP, None]]:
        record_id = int(interaction.message.embeds[0].footer.text.split('ID:')[1])
        try:
            record_rp: RecordsToRP = RecordsToRP.select() \
                .join(UserDiscord, on=(UserDiscord.id == RecordsToRP.player_id)) \
                .where(RecordsToRP.record_rp_id == record_id) \
                .get()
        except peewee.DoesNotExist:
            await interaction.response.send_message(f'Что-то пошло не так, чорт...')
            raise peewee.DoesNotExist('Request does not exists')

    @discord.ui.button(label="Принять заявку", custom_id="sunrise_button_for_change_record:success",
                       style=discord.ButtonStyle.success, emoji=discord.PartialEmoji.from_str("✅"))
    async def approve_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        record_rp = self.get_user_record(interaction)

        user = interaction.client.get_user(record_rp.player_id.discord_id)
        channel: discord.DMChannel = await user.create_dm() if not user.dm_channel else user.dm_channel
        message: discord.Message = await channel.fetch_message(record_rp.message_id)
        embed = message.embeds[0]
        embed.add_field(name='Заявка подтверждена!', value=f'`{interaction.user.name}#'
                                                           f'{interaction.user.discriminator}` принял Вашу заявку на '
                                                           f'участие в РП-Сессии!')
        view: ButtonViewForRecordRPSession = discord.ui.View.from_message(message) # noqa
        view.change_record.disabled = False
        await message.edit(view=view, embed=embed)
        await channel.send('Ваша заявка подтверждена!')

        self.approve_record.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Отклонить заявку", custom_id="sunrise_button_for_delete_record:danger",
                       style=discord.ButtonStyle.danger, emoji=discord.PartialEmoji.from_str("❌"))
    async def discharge_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        record_rp = self.get_user_record(interaction)

        user = interaction.client.get_user(record_rp.player_id.discord_id)
        channel: discord.DMChannel = await user.create_dm() if not user.dm_channel else user.dm_channel
        message: discord.Message = await channel.fetch_message(record_rp.message_id)
        view: ButtonViewForRecordRPSession = discord.ui.View.from_message(message)  # noqa
        view.change_record.disabled = False
        await message.edit(view=view)

        self.approve_record.disabled = True
        await interaction.message.edit(view=self)

class ButtonViewForRecordRPSession(discord.ui.View):
    def __init__(self):
        super(ButtonViewForRecordRPSession, self).__init__(timeout=None)

    @discord.ui.button(label="Изменить заявку", custom_id="sunrise_button_for_change_record:secondary",
                       style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str("🖊️"),
                       disabled=True)
    async def change_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Отменить заявку", custom_id="sunrise_button_for_delete_record:danger",
                       style=discord.ButtonStyle.danger, emoji=discord.PartialEmoji.from_str("🆑"))
    async def delete_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class MakeRecordToRPSession(discord.ui.Modal, title='Запись на РП-Сессию'):
    train = discord.ui.TextInput(
        label="Подвижной состав",
        placeholder="81-717/81-720/81-710 и т.д.",
        style=discord.TextStyle.short,
        required=True
    )

    time = discord.ui.TextInput(
        label="Временные рамки вашего участия",
        placeholder="Вся РП-Сессия/На 1 час/На последний час и т.д.",
        style=discord.TextStyle.short,
        required=True
    )

    comment = discord.ui.TextInput(
        label="Комментарий",
        placeholder="Пожелания к кастомизации или еще что-нибудь...",
        style=discord.TextStyle.long,
        required=False
    )

    def __init__(self):
        super(MakeRecordToRPSession, self).__init__(timeout=60.0)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        try:
            await interaction.user.send()
        except discord.HTTPException as e:
            if e.code == 50007:
                await interaction.response.send_message("Вам невозможно отправить личное сообщение! "
                                                        "Пожалуйста проверьте, что ваши ЛС открыты для бота!\nА до "
                                                        "того момента **ЗАПИСЬ ОТКЛОНЕНА** или **ОБРАТИТЕСЬ К "
                                                        "ОРГАНИЗАТОРУ РП-СЕССИИ**")
                return
            elif e.code == 50006:
                pass
            else:
                raise

        try:
            discord_user = UserDiscord.get(UserDiscord.discord_id == interaction.user.id)
        except peewee.DoesNotExist:
            UserDiscord.insert(discord_id=interaction.user.id).on_conflict_ignore().execute()
            Fortune.insert(discordID=interaction.user.id).on_conflict_ignore().execute()
            discord_user = UserDiscord.get(UserDiscord.discord_id == interaction.user.id)

        await interaction.response.defer()

        rp_session: RPSession = RPSession.get(RPSession.message_id == interaction.message.id)

        record_to_rp: RecordsToRP = RecordsToRP.insert(
            rp_session_id=rp_session,
            player_id=discord_user,
            message_id=0,
            is_approve=False,
            time=self.time.value,
            train=self.train.value,
            comment=self.comment.value if self.comment.value else None).execute()

        fields = [
            {'title': 'Название сессии',
             'text': rp_session.name_rp},
            {'title': 'Дата и время сессии',
             'text': f'<t:{int(rp_session.start_datetime.timestamp())}:f>'},
            {'title': 'Тип подвижного состава',
             'text': self.train.value},
            {'title': 'Время участия в РП-Сессии',
             'text': self.time.value},
            {'title': 'Комментарий',
             'text': self.comment.value if self.comment.value else 'Отсутствует'}
        ]

        fields_org = [
            {'title': 'Тип подвижного состава:',
             'text': self.train.value},
            {'title': 'Время участия в РП-Сессии:',
             'text': self.time.value},
            {'title': 'Комментарий',
             'text': self.comment.value if self.comment.value else 'Отсутствует'}
        ]

        embed = await interaction.client.embed(title="Вы успешно записаны на РП-Сессию",
                                               text=f"{interaction.user.mention}, вы записаны на РП-Сессию!",
                                               fields=fields,
                                               icon_url=interaction.guild.icon.url,
                                               footer=f'ID:{record_to_rp}')
        channel = await interaction.user.create_dm()
        message_id = await channel.send(embed=embed, view=ButtonViewForRecordRPSession())
        record_to_rp.message_id = message_id
        record_to_rp.save()

        embed_org = await interaction.client.embed(title=f'Пользователь {interaction.user.name}'
                                                         f'#{interaction.user.discriminator} записался на РП-Сессию',
                                                   text='От Вас, как от организатора требует либо **ПРИНЯТЬ**, либо '
                                                        '**ОТКЛОНИТЬ** заявку данного игрока. Ниже предоставлена '
                                                        'информация по заявке',
                                                   fields=fields_org,
                                                   icon_url=interaction.guild.icon.url,
                                                   footer=f'ID:{record_to_rp}')

        member: discord.Member = interaction.guild.get_member(int(rp_session.org_id))
        channel = await member.create_dm()
        await channel.send(embed=embed_org, view=ButtonViewOrganizerOfRPSession())

    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        interaction.client.log.error(error)


class RPSessionButtonsView(discord.ui.View):
    def __init__(self):
        super(RPSessionButtonsView, self).__init__(timeout=None)

    @discord.ui.button(label="Открыть запись", custom_id="sunrise_button_for_open_requests:success",
                       style=discord.ButtonStyle.success, emoji=discord.PartialEmoji.from_str("🔓"),
                       row=1)
    async def open_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            rpsession = RPSession.get(RPSession.message_id == interaction.message.id)
        except peewee.DoesNotExist:
            await interaction.response.send_message("Ошибка! Не найдена РП-Сессия в базе данных. "
                                                    "Удалите это сообщение и создайте анонс заново!",
                                                    ephemeral=True)
            return

        if not interaction.user.guild_permissions.ban_members \
                and not interaction.user.guild_permissions.manage_channels:
            interaction.response.send_message('```Не тыкай на кнопку, сладкий, у тебя прав нет. '
                                              'Иначе ляпис крюе тебя найдет, забанит, а потом съест```',
                                              ephemeral=True)

        await interaction.response.defer()

        self.make_record_rp.disabled = False
        self.open_requests.disabled = True
        self.close_requests.disabled = False
        self.close_rpsession.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Закрыть запись", custom_id="sunrise_button_for_close_requests:secondary",
                       style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str("🔐"),
                       disabled=True, row=1)
    async def close_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            rpsession = RPSession.get(RPSession.message_id == interaction.message.id)
        except peewee.DoesNotExist:
            await interaction.response.send_message("Ошибка! Не найдена РП-Сессия в базе данных. "
                                                    "Удалите это сообщение и создайте анонс заново!",
                                                    ephemeral=True)
            return

        if not interaction.user.guild_permissions.ban_members \
                and not interaction.user.guild_permissions.manage_channels:
            interaction.response.send_message('```Дурной, ты кнопкой ошибся — твоя кнопка ниже. '
                                              'Давай записывайся, если ты этого еще не сделал.```',
                                              ephemeral=True)

        await interaction.response.defer()

        self.make_record_rp.disabled = True
        self.open_requests.disabled = False
        self.close_requests.disabled = True
        self.close_rpsession.disabled = False
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Закончить РП-Сессию", custom_id="sunrise_button_for_close_session:danger",
                       style=discord.ButtonStyle.danger, emoji=discord.PartialEmoji.from_str("🚇"),
                       disabled=True, row=1)
    async def close_rpsession(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            rpsession = RPSession.get(RPSession.message_id == interaction.message.id)
        except peewee.DoesNotExist:
            await interaction.response.send_message("Ошибка! Не найдена РП-Сессия в базе данных. "
                                                    "Удалите это сообщение и создайте анонс заново!",
                                                    ephemeral=True)
            return

        if not interaction.user.guild_permissions.ban_members \
                and not interaction.user.guild_permissions.manage_channels:
            interaction.response.send_message('```Закрыть РП-Сессию собрался? Тебя что-то не устраивает? '
                                              'Всегда можно пожаловаться нашему НАЧАЛЬНИКУ МЕТРОПОЛИТЕНА!```',
                                              ephemeral=True)

        await interaction.response.defer()

        self.open_requests.disabled = True
        self.close_requests.disabled = True
        self.close_rpsession.disabled = True
        self.make_record_rp.disabled = True
        await interaction.message.edit(view=self)

        rpsession.is_active = False
        rpsession.save()

    @discord.ui.button(label="Записаться", custom_id="sunrise_button_for_make_record:success",
                       style=discord.ButtonStyle.success, emoji=discord.PartialEmoji.from_str("✍️"),
                       disabled=True, row=2)
    async def make_record_rp(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            record_to_rp: RecordsToRP = RecordsToRP \
                .select() \
                .join(RPSession, on=(RPSession.rp_session_id == RecordsToRP.rp_session_id)) \
                .join(UserDiscord, on=(UserDiscord.id == RecordsToRP.player_id)) \
                .where((RPSession.message_id == interaction.message.id)
                       & (UserDiscord.discord_id == interaction.user.id)) \
                .get()
        except peewee.DoesNotExist:
            await interaction.response.send_modal(MakeRecordToRPSession())
            message: discord.Message = interaction.message
            embed = message.embeds[0].to_dict()
            if embed['fields'][1]['value'] == '¯\_(ツ)_/¯':
                embed['fields'][1]['value'] = interaction.user.mention
            else:
                embed['fields'][1]['value'] += f"\n{interaction.user.mention}"
            await message.edit(embed=discord.Embed.from_dict(embed))
        else:
            if record_to_rp.is_approve:
                embed = await interaction.client.embed(
                    title="Запись на РП-Сессию уже произведена и одобрена!",
                    text="Вы уже записаны на РП-Сессию! Если вы хотите отменить заявку, то пожалуйста загляните в "
                         "наши личные сообщения!")
            else:
                embed = await interaction.client.embed(
                    title="Запись на РП-Сессию уже произведена, но пока не одобрена!",
                    text="Вы уже записаны на РП-Сессию, но Вам осталось только дождаться одобрения записи на "
                         "РП-Сессию от организатора! Если же вы хотите отменить заявку, пожалуйста, загляните в "
                         "наши личные сообщения!")

            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception,
                       item: discord.ui.Item[Any], /) -> None:
        interaction.client.log.error(f"Error: {error}\nItem: [{item.type} | {item.label}]")


class RPSessionModal(discord.ui.Modal, title="Анонсировать РП-Сессию"):
    name_rp = discord.ui.TextInput(
        label="Название РП-Сессии",
        style=discord.TextStyle.short,
        required=True
    )

    datetime = discord.ui.TextInput(
        label="Дата и время начала РП-Сессии",
        placeholder="ДД.ММ.ГГГГ ЧЧ:ММ",
        style=discord.TextStyle.short,
        required=True
    )

    map = discord.ui.TextInput(
        label="Карта РП-Сессии",
        style=discord.TextStyle.short,
        required=True
    )

    comment = discord.ui.TextInput(
        label="Комментарий",
        style=discord.TextStyle.long,
        required=False
    )

    validate_datetime: datetime

    def __init__(self):
        super(RPSessionModal, self).__init__(timeout=15.0)

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        try:
            self.validate_datetime = datetime.strptime(self.datetime.value, "%d.%m.%Y %H:%M")
        except ValueError:
            await interaction.response.send_message("Дата указана в неверном формате!"
                                                    "\nПример даты и времени: `10.05.2023 17:30`")
            return False
        else:
            return True

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        bot: Katherine = interaction.client  # noqa
        await interaction.response.defer()

        fields: list = [
            {'title': 'Записавшиеся:',
             'text': '¯\_(ツ)_/¯'},
            {'title': 'На одобрении:',
             'text': '¯\_(ツ)_/¯'}
        ]

        if self.comment.value:
            fields.append({
                'title': 'Доп. информация',
                'text': self.comment.value
            })

        embed = await bot.embed(title=self.name_rp.value,
                                text=f"**Привет! А вот и анонс на РП-Сессию!**\n\n"
                                     f"• Дата: {discord.utils.format_dt(self.validate_datetime, style='d')} 📆\n"
                                     f"• Карта: {self.map} 🚇\n"
                                     f"• Начало РП-Сессии: "
                                     f"{discord.utils.format_dt(self.validate_datetime, style='t')} 🕐\n\n"
                                     f"🔻 К ознакомлению обязательно:\n"
                                     f"📄 График движения поездов и разбивка\n"
                                     f"А его не будет, сколько запишется людей - столько и поедет\n"
                                     f"Но надо минимум 5 машинистов для проведения РП-сессию\n\n"
                                     f"🔻Записываясь на RP-сессию, вы берёте ответственность и гарантируете участие в "
                                     f"указанное время!\n\n"
                                     f"🔸 За час до начала поездки пришлём дополнительное уведомление тем, кто "
                                     f"записался на сессию\n"
                                     f"🔸 Запись на РП сессию производится через наш Discord в канале #запись-на-рп\n\n"
                                     f"⭐️Данная РП-сессия предназначена для всех игроков нашего сообщества, чтобы они "
                                     f"смогли себя почувствовать машинистами реального метрополитена\n"
                                     f"⭐️ Все игроки, которые хорошо откатают всю РП-сессию получат крутой бонус "
                                     f"(это наш маленький секретик)",
                                color=discord.Colour.from_rgb(204, 109, 0),
                                thumbnail=interaction.guild.icon.url,
                                fields=fields)

        message = await interaction.channel.send(  # content="||@everyone||",
            embed=embed,
            view=RPSessionButtonsView())

        RPSession.insert(is_active=True,
                         name_rp=self.name_rp.value,
                         start_datetime=self.validate_datetime,
                         message_id=message.id,
                         org_id=interaction.user.id,
                         map_name=self.map,
                         comment=self.comment.value if self.comment.value else None).execute()

    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        interaction.client.log.error(error)
        await interaction.channel.send(f"Произошло непредвиденное исключение!\nОшибка — `{error}`",
                                       ephemeral=True)


class RPSessionCog(AbstractCog, name="Система РП-Сессий"):
    @app_commands.command(name="анонс",
                          description="Создает анонс РП-Сессии и открывает доступ к заявкам")
    @app_commands.checks.cooldown(1, 15, key=lambda interaction: interaction.user.id)
    @app_commands.default_permissions(manage_messages=True, manage_channels=True)
    @app_commands.check(AbstractCog.reconnect)
    async def announcement(self, interaction: discord.Interaction):
        try:
            RPSession.get(RPSession.is_active == True)
        except peewee.DoesNotExist:
            await interaction.response.send_modal(RPSessionModal())
        else:
            await interaction.response.send_message("РП-Сессия уже создана! Закройте предыдущую, чтобы создать новую!",
                                                    ephemeral=True)


async def setup(client):
    await client.add_cog(RPSessionCog(client))
