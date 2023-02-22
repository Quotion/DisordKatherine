import os
import datetime
import traceback

import discord
import requests
import steam.steamid
import functions.helper

from io import BytesIO
from valve.rcon import *  # noqa
from peewee import fn, JOIN
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw

from utils.context import Context
from utils.models import *

from main import Katherine, AbstractCog


class ModalChoice(discord.ui.Modal):
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

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        ctx: Context = await interaction.client.get_context(interaction.message)  # noqa
        await ctx.supplement()

        answers = self.answers.value.split("+")

        if len(answers) > 9 or len(answers) < 1:
            await interaction.response.send_message(
                embed=await ctx.embed_message(
                    f"Ответов очень {'мало' if len(answers) < 1 else 'много'}.",
                    f"Голосование не может быть создано, потому что количество "
                    f"ответов {'меньше 1' if len(answers) < 1 else 'больше 9'}."))
            return

        await interaction.response.defer()

        msg = await interaction.channel.send(embed=await AbstractCog.reconnect.poll(ctx, self.question.value, answers))

        for i in range(1, len(answers) + 1):
            await msg.add_reaction(f"{i}\N{combining enclosing keycap}")


class ProfileViewSunrise(discord.ui.View):
    def __init__(self, inter_member: discord.Member, viewed_member: discord.Member, *args, **kwargs):
        super(ProfileViewSunrise, self).__init__(*args, **kwargs)

        if inter_member.id == viewed_member.id:
            self.inter_member: discord.Member = inter_member
            self.viewed_member: discord.Member = inter_member
        else:
            self.inter_member: discord.Member = inter_member
            self.viewed_member: discord.Member = viewed_member

    @discord.ui.button(label="Счёт", style=discord.ButtonStyle.success,
                       emoji=discord.PartialEmoji.from_str("💸"), custom_id="get_money_in_sunrise:success")
    async def money_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user: UserDiscord = UserDiscord.get(UserDiscord.discord_id == interaction.user.id)
        except peewee.DoesNotExist as error:
            # logger.debug(error)
            return

        if interaction.user.id != self.inter_member.id and interaction.user.id != self.viewed_member.id:  # noqa
            await interaction.response.defer()
            await interaction.message.delete()
            return

        await interaction.message.delete()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        ctx: Context = await interaction.client.get_context(interaction.message)  # noqa
        await ctx.supplement()

        background = Image.open("static/profiles/money.jpg")
        request = requests.get(self.viewed_member.avatar.url)
        avatar = Image.open(BytesIO(request.content))

        avatar_background = avatar.resize((200, 200), Image.ANTIALIAS)
        background.paste(avatar_background, (120, 50))

        avatar.close()
        avatar_background.close()

        draw = ImageDraw.Draw(background)  # noqa

        name = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 50, encoding="unic")  # noqa
        display_name = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 35, encoding="unic")  # noqa
        money = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 35)

        if self.viewed_member.display_name == self.viewed_member.name:
            draw.text((337, 203), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (50, 50, 50),
                      font=name)
            draw.text((335, 200), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (255, 255, 255),
                      font=name)
        else:
            draw.text((337, 153), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (50, 50, 50),
                      font=name)
            draw.text((335, 150), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (255, 255, 255),
                      font=name)
            draw.text((337, 208), self.viewed_member.display_name, (50, 50, 50), font=display_name)
            draw.text((335, 205), self.viewed_member.display_name, (255, 255, 255), font=display_name)

        draw.text((123, 398), f"Средства: {user.money} рев.", (50, 50, 50), font=money)
        draw.text((120, 395), f"Средства: {user.money} рев.", (255, 255, 255), font=money)
        draw.text((298, 438), f"{user.gold_money} зл. рев.", (50, 50, 50), font=money)
        draw.text((295, 435), f"{user.gold_money} зл. рев.", (255, 255, 255), font=money)

        try:
            dynamic = Dynamic \
                .select((fn.SUM(Dynamic.money) * 100 / UserDiscord.money).alias("percent_money"),
                        (fn.SUM(Dynamic.gold_money) * 100 / UserDiscord.gold_money).alias("percent_gold_money"),
                        fn.MIN(Dynamic.time).alias("time"),
                        UserDiscord.money,
                        UserDiscord.gold_money) \
                .join(UserDiscord, on=(Dynamic.discord == UserDiscord.discord_id)) \
                .where((Dynamic.discord == self.viewed_member.id) & (peewee.SQL("DATE_SUB(NOW(), INTERVAL 7 day)"))) \
                .get()
        except peewee.DoesNotExist:
            dynamic = 0

        if dynamic == 0 or not dynamic.percent_money:
            draw.text((123, 523), f"Динамика: -", (50, 50, 50), font=money)
            draw.text((120, 520), f"Динамика: -", (255, 255, 255), font=money)
            draw.text((311, 563), f"-", (50, 50, 50), font=money)
            draw.text((308, 560), f"-", (255, 255, 255), font=money)
        else:
            green_arrow = Image.open("static/images/green_arrow.png")
            red_arrow = Image.open("static/images/red_arrow.png")

            if dynamic.percent_money >= 0:
                draw.text((123, 523), f"Динамика: {round(dynamic.percent_money, 2)}%    "
                                      f"    c {time.strftime('%d.%m.%Y')}",
                          (50, 50, 50),
                          font=money)
                draw.text((120, 520), f"Динамика: {round(dynamic.percent_money, 2)}%    "
                                      f"    c {time.strftime('%d.%m.%Y')}",
                          (255, 255, 255),
                          font=money)

                green_arrow_background = green_arrow.resize((20, 35))
                background.paste(green_arrow_background, (450, 520), mask=green_arrow_background)

            elif dynamic.percent_money < 0:
                draw.text((123, 523),
                          f"Динамика: {round(dynamic.percent_money, 2)}%        c {time.strftime('%d.%m.%Y')}",
                          (50, 50, 50),
                          font=money)
                draw.text((120, 520),
                          f"Динамика: {round(dynamic.percent_money, 2)}%        c {time.strftime('%d.%m.%Y')}",
                          (255, 255, 255),
                          font=money)

                red_arrow_background = red_arrow.resize((20, 35), Image.ANTIALIAS)
                background.paste(red_arrow_background, (450, 520), mask=red_arrow_background)

            if dynamic.percent_gold_money >= 0:
                draw.text((313, 563), f"{round(dynamic.percent_gold_money, 2)}%", (50, 50, 50), font=money)
                draw.text((310, 560), f"{round(dynamic.percent_gold_money, 2)}%", (255, 255, 255), font=money)

                green_arrow_background = green_arrow.resize((20, 35))
                background.paste(green_arrow_background, (450, 560), mask=green_arrow_background)

            elif dynamic.percent_gold_money < 0:
                draw.text((313, 563), f"{round(dynamic.percent_gold_money, 2)}%", (50, 50, 50), font=money)
                draw.text((310, 560), f"{round(dynamic.percent_gold_money, 2)}%", (255, 255, 255), font=money)

                red_arrow_background = red_arrow.resize((20, 35), Image.ANTIALIAS)
                background.paste(red_arrow_background, (450, 560), mask=red_arrow_background)

        background.save("static/buff/money.jpg", quality=100)

        background.close()
        request.close()

        discord_file = discord.File("static/buff/money.jpg", filename="money.jpg")

        await message.edit(
            content=None,
            embed=await ctx.embed_message(title="Ниже представлена вся необходимая информация",
                                          text="Вся необходимая информация о деньгах, которые есть на вашем счету, "
                                               "представлена ниже",
                                          icon_url=interaction.guild.icon.url,
                                          thumbnail="https://thumbnailer.mixcloud.com/unsafe/1200x628/profile/e/d/5/f/"
                                                    "dc8c-8924-4404-b379-6e0290002c92",
                                          image="attachment://money.jpg"),
            attachments=[discord_file])

        discord_file.close()

        try:
            os.remove("static/buff/money.jpg")
        except Exception:  # noqa
            discord_file.close()
            os.remove("static/buff/money.jpg")

    @discord.ui.button(label="Данные с сервера", style=discord.ButtonStyle.blurple,
                       emoji=discord.PartialEmoji.from_str("✔️"), custom_id="user_server_info:blurple")
    async def server_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user: UserDiscord = UserDiscord.get(UserDiscord.discord_id == self.viewed_member.id)

        if interaction.user.id != self.inter_member.id and interaction.user.id != self.viewed_member.id:  # noqa
            await interaction.response.defer()
            await interaction.message.delete()
            return

        await interaction.message.delete()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        ctx: Context = await interaction.client.get_context(interaction.message)  # noqa
        await ctx.supplement()

        if user.SID == "None" or not user.SID:
            return None, None, None

        try:
            gmod_user: GmodPlayer = GmodPlayer.get(GmodPlayer.SID == user.SID)
        except peewee.DoesNotExist as error:
            # logger.debug(error)
            return None, None, None

        try:
            sum_tm = PlayerGroupTime \
                .select(fn.SUM(PlayerGroupTime.time)
                        .alias('sum_time')) \
                .where(PlayerGroupTime.player_id == gmod_user.id) \
                .get()
        except Exception as error:
            # logger.error(error)
            return None, None, None

        all_time = str(timedelta(seconds=int(sum_tm.sum_time)))  # noqa
        if all_time.find("days") != -1:
            all_time = all_time.replace("days", "дн")
        else:
            all_time = all_time.replace("day", "дн")

        if all_time.find("weeks") != -1:
            all_time = all_time.replace("weeks", "нед")
        else:
            all_time = all_time.replace("week", "нед")

        background = Image.open("static/profiles/server.jpg")
        request = requests.get(self.viewed_member.display_avatar.url)
        avatar = Image.open(BytesIO(request.content))

        avatar_background = avatar.resize((200, 200), Image.ANTIALIAS)
        background.paste(avatar_background, (120, 50))

        draw = ImageDraw.Draw(background)

        name = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 50, encoding="unic")  # noqa
        display_name = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 35, encoding="unic")  # noqa
        server = ImageFont.truetype("static/fonts/RobotoRegular.ttf", 35)

        if self.viewed_member.display_name == self.viewed_member.name:
            draw.text((337, 203), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (50, 50, 50),
                      font=name)
            draw.text((335, 200), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (255, 255, 255),
                      font=name)
        else:
            draw.text((337, 153), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (50, 50, 50),
                      font=name)
            draw.text((335, 150), f"{self.viewed_member.name}#{self.viewed_member.discriminator}", (255, 255, 255),
                      font=name)
            draw.text((337, 208), self.viewed_member.display_name, (50, 50, 50), font=display_name)
            draw.text((335, 205), self.viewed_member.display_name, (255, 255, 255), font=display_name)

        draw.text((123, 398), f"Nickname: {gmod_user.nick}", (50, 50, 50), font=server)
        draw.text((120, 395), f"Nickname: {gmod_user.nick}", (255, 255, 255), font=server)

        if gmod_user.group == "user":
            draw.text((123, 438), f"Rank: Машинист электропоезда", (50, 50, 50), font=server)
            draw.text((120, 435), f"Rank: Машинист электропоезда", (255, 255, 255), font=server)
        elif gmod_user.group == "user+":
            draw.text((123, 438), "Rank: Машинист электропоезда+", (50, 50, 50), font=server)
            draw.text((120, 435), "Rank: Машинист электропоезда+", (255, 255, 255), font=server)
        elif gmod_user.group == "operator":
            draw.text((123, 438), "Rank: Модератор", (50, 50, 50), font=server)
            draw.text((120, 435), "Rank: Модератор", (255, 255, 255), font=server)
        elif gmod_user.group == "admin":
            draw.text((123, 438), "Rank: Почетный игрок", (50, 50, 50), font=server)
            draw.text((120, 435), "Rank: Почетный игрок", (255, 255, 255), font=server)
        elif gmod_user.group == "superadmin":  # noqa
            draw.text((123, 438), "Rank: Президент мира", (50, 50, 50), font=server)
            draw.text((120, 435), "Rank: Президент мира", (255, 255, 255), font=server)

        draw.text((123, 523), f"SteamID: {gmod_user.SID}", (50, 50, 50), font=server)  # noqa
        draw.text((120, 520), f"SteamID: {gmod_user.SID}", (255, 255, 255), font=server)

        draw.text((123, 563), f"Общее время игры: {all_time}", (50, 50, 50), font=server)
        draw.text((120, 560), f"Общее время игры: {all_time}", (255, 255, 255), font=server)

        background.save("static/buff/server.jpg", quality=100)

        background.close()
        request.close()

        discord_file = discord.File("static/buff/server.jpg", filename="server.jpg")

        if not discord_file:
            await message.edit(
                embed=await ctx.embed_message(title="Не синхронизирован.",
                                              text="Похоже, что вы не синхронизировали свой Discord с Garry's mod-ом."
                                                   "\n\nЧтобы сделать это введите команду\n`/синхр <SteamID или "
                                                   "Ссылку на steam>`",
                                              icon_url=interaction.guild.icon))

        else:
            await message.edit(
                content=None,
                embed=await ctx.embed_message(title="Ниже представлена вся необходимая информация",
                                              text=f"Ваши данные с сервера Sunrise Metrostroi:\n\n**Rank**: "
                                                   f"`{gmod_user.group}`\n**SteamID**: `{gmod_user.SID}`",
                                              icon_url=interaction.guild.icon,
                                              thumbnail="https://w7.pngwing.com/pngs/792/889/png-transparent-computer-"
                                                        "icons-computer-servers-data-center-server-miscellaneous-"
                                                        "angle-electronics.png",
                                              image="attachment://server.jpg"),
                attachments=[discord_file])

            discord_file.close()

            try:
                os.remove("static/buff/server.jpg")
            except:  # noqa
                discord_file.close()
                os.remove("static/buff/server.jpg")

    @discord.ui.button(label="МП-Информация", style=discord.ButtonStyle.blurple, disabled=True,
                       emoji=discord.PartialEmoji.from_str("🤸"), custom_id="mp_server_sunrise:blurple")
    async def mp_server_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class MainCommands(AbstractCog, name="Основные команды"):

    def __init__(self, client):  # noqa
        self.client: Katherine = client
        self.start = int(time.time())

        self.choice_on = False

    @commands.check(AbstractCog.reconnect)  # noqa
    def profile_check():  # noqa
        def predicate(interaction):
            UserDiscord.insert(discord_id=interaction.author.id).on_conflict_ignore().execute()
            Fortune.insert(discordID=interaction.author.id).on_conflict_ignore().execute()
            return True

        return commands.check(predicate)

    @app_commands.command(name='профиль',
                          description="Дает доступ к информации о Вас или о др. пользователе")
    @app_commands.describe(member="Пользователь, профиль которого нужно посмотреть.")
    @app_commands.checks.cooldown(1, 20, key=lambda interaction: interaction.user.id)
    @profile_check()
    async def profile(self, interaction: discord.Interaction, *, member: discord.Member = None):
        try:
            ctx: Context = await self.client.get_context(interaction)
            await ctx.supplement()
        except:
            print(traceback.format_exc())

        if not member:
            member: discord.Member = interaction.user

        embed_fields = ({"title": "Ваши средства на счету 🤑",
                         "text": "Показывает ваши средства на счету, а также статистику изменения его за неделю."},
                        {"title": "Информация о Вас \uD83E\uDD38\u200D♂️",
                         "text": "Ваш последняя информация, т.е. ранг, SteamID и имя на серверах Sunrise Metrostroi."},
                        {"title": "Информация о Вас с РП-серверов \uD83D\uDE86",
                         "text": "Сколько баллов у вас есть, какой ранг вы имеете."})

        await interaction.response.send_message(
            embed=await ctx.embed_message(title=f"Профиль пользователя {member.name}#{member.discriminator}",
                                          text="Если вы хотите посмотреть свой профиль, просто выберите один из 3 "
                                               "предложенных вариантов, чтобы увидеть всю необходимую информацию",
                                          icon_url=interaction.guild.icon,
                                          thumbnail=member.avatar,
                                          fields=embed_fields),
            view=ProfileViewSunrise(inter_member=interaction.user, viewed_member=member))

    @app_commands.command(name="шанс",
                          description="Команда для получения ежедневной прибыли (3 раза в день).")
    @app_commands.checks.cooldown(1, 5, key=lambda interaction: interaction.user.id)
    @app_commands.check(AbstractCog.reconnect)  # noqa
    @profile_check()
    async def chance(self, interaction: discord.Interaction):
        ctx: Context = await self.client.get_context(interaction)
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        now = datetime.now()

        with open("static/config.json", "r", encoding="utf8") as config_file:
            config = js.load(config_file)

        if config['now_date'] != now.strftime("%d.%m.%Y"):
            config['now_date'] = now.strftime("%d.%m.%Y")
            Fortune.update({Fortune.chance: 3}).where(not Fortune.chance).execute()

        user: UserDiscord = UserDiscord.get(UserDiscord.discord_id == ctx.author.id)
        fortune: Fortune = Fortune.get(Fortune.discord == ctx.author.id)

        with open("static/config.json", "w", encoding="utf8") as config_file:
            js.dump(config, config_file, indent=4)

        if not fortune.chance:
            tomorrow = datetime.now() + timedelta(days=1)

            time_to = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)

            await message.edit(
                content=None,
                embed=await ctx.embed_message("Активация шанса уже была использована полностью.",
                                              f"Вы сможете воспользоваться командой, когда наступит "
                                              f"<t:{int(time_to.timestamp())}:F>."))
            return

        fortune.chance = fortune.chance - 1
        fortune.save()

        times = f"{fortune.chance} раза" if fortune.chance > 1 else f"{fortune.chance} раз"

        win, thing = await functions.helper.random_win()

        if thing == 0:
            user.money = user.money + win  # noqa
            user.save()
            await message.edit(
                content=None,
                embed=await ctx.embed_message(f"Шанс использован. Осталось {times}.",
                                              f"Сегодня ваш куш составил **{win} рев.** Но мы уверены, что в следующий "
                                              f"раз вы получите больше!\n\nВаш Sunrise Metrostroi.",
                                              footer=ctx.guild.name + "  •  " + ctx.channel.name,
                                              color=discord.Colour.random(), thumbnail=interaction.guild.icon.url))
        elif thing == 1:
            user.gold_money = user.gold_money + win  # noqa
            user.save()
            await message.edit(
                content=None,
                embed=await ctx.embed_message(f"Шанс использован. Осталось {times}.",
                                              f"Сегодня ваш куш составил **{win} зл. рев.** Но мы уверены, что в "
                                              f"следующий раз вы получите больше!\n\nВаш Sunrise Metrostroi.",
                                              footer=ctx.guild.name + "  •  " + ctx.channel.name,
                                              color=discord.Colour.random(), thumbnail=interaction.guild.icon.url))

    @app_commands.command(name="рулетка",
                          description="Команда для получения случ. выигрыша")
    @app_commands.describe(rate="Количество реверсивок для рулетки")
    @app_commands.checks.cooldown(1, 5, key=lambda interaction: interaction.user.id)
    @app_commands.check(AbstractCog.reconnect)  # noqa
    @profile_check()
    async def roulette(self, interaction: discord.Interaction, rate: int):
        ctx: Context = await self.client.get_context(interaction)
        await ctx.supplement()

        if rate > 1000000:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Превышена ставка для рулетки",
                                              "Пожалуйста уменьшите ставку до **1 000 000 зл. реверсивок**"))
            return

        user = UserDiscord.get(UserDiscord.discord_id == ctx.author.id)

        if user.gold_money < rate:
            await interaction.response.send_message(
                embed=await ctx.embed_message("Недостаточно зл. реверсивок!",
                                              "Количество введенной суммы реверсивок недостаточно для "
                                              "выполнения данной команды."))
            return

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        win = int(await functions.helper.factor_win() * rate)
        gif = "https://cdn.dribbble.com/users/2206179/screenshots/8185041/roulette_ball_v2_compress.gif"

        if 0 < win / rate <= 0.2:
            text = f"{interaction.user.mention} проиграл всю поставленную сумму, как прискорбно." \
                   f"\n\n**Остаточная сумма: {win} зл. реверсивок**\n\nВаш Sunrise Metrostroi"
            gif = "https://j.gifs.com/rRo702.gif"
        elif 0.2 < win / rate <= 0.5:
            text = f"{interaction.user.mention} не повезло и он получил всего ничего.\n\n**Остаточная сумма: {win} " \
                   f"зл. реверсивок**\n\nВаш Sunrise Metrostroi"
            gif = "https://j.gifs.com/rRo702.gif"
        elif 1.1 < win / rate <= 2:
            text = f"{interaction.user.mention} выиграл в рулетке и получил назад не только сумму ставки, " \
                   f"но еще и кэш.\n\n**Сумма выигрыша: {win} зл. реверсивок**\n\nВаш Sunrise Metrostroi"
        elif 2 < win / rate <= 3:
            text = f"{interaction.user.mention} сорвал куш и победил саму судьбу в игре под названием Фортуна. " \
                   f"Как вам такое Борис Сергеевич?\n\n**Сумма выигрыша: {win} зл. реверсивок**" \
                   f"\n\nВаш Sunrise Metrostroi"
        else:
            text = f"{interaction.user.mention}, страшно. Очень страшно.\nЕсли бы мы знали, мы не знаем что это " \
                   f"такое, если бы мы знали что это такое, мы не знаем что это такое." \
                   f"\n\n**Остаточная сумма: {win} зл. реверсивок**\n\nВаш Sunrise Metrostroi"

        user.gold_money = user.gold_money - rate + win
        user.save()

        await message.edit(
            embed=await ctx.embed_message("Рулетка активирована", text,
                                          footer=ctx.guild.name + "  •  " + ctx.channel.name,
                                          color=discord.Colour.random(),
                                          image=gif))

    @app_commands.command(name="топ")
    @app_commands.checks.cooldown(1, 5, key=lambda interaction: interaction.user.id)
    @commands.check(AbstractCog.reconnect)  # noqa
    async def top(self, interaction: discord.Interaction):
        ctx: Context = await self.client.get_context(interaction)
        await ctx.supplement()

        await interaction.response.send_message("***Ожидайте...***")
        message: discord.InteractionMessage = await interaction.original_response()

        all_data = list()

        data = PlayerGroupTime \
            .select(PlayerGroupTime.player_id, fn.SUM(PlayerGroupTime.time).alias('sum_time')) \
            .join(GmodPlayer, JOIN.LEFT_OUTER) \
            .group_by(PlayerGroupTime.player_id) \
            .order_by(fn.SUM(PlayerGroupTime.time).desc()) \
            .limit(10)

        embed = discord.Embed(colour=discord.Colour.dark_gold())
        embed.set_author(name="ТОП 10 игроков сервера {}".format(ctx.guild.name))

        for info, count in zip(data, range(10)):
            link = steam.steamid.SteamID(info.player_id.SID)

            time = str(timedelta(seconds=int(info.sum_time)))  # noqa
            if time.find("days") != -1:
                timestamp = time.replace("days", "дн")
            else:
                timestamp = time.replace("day", "дн")

            if timestamp.find("weeks") != -1:
                timestamp = timestamp.replace("weeks", "нед")
            else:
                timestamp = timestamp.replace("week", "нед")
            all_data.append(f"{count + 1}. [{info.player_id.nick}]({link.community_url}) "
                            f"({info.player_id.SID}) - {timestamp}")

        embed.description = '\n'.join([one_man for one_man in all_data])

        await message.edit(embed=embed)

    @app_commands.command(name="обмен",
                          description="Обмен реверсивками по формуле 4:1")
    @app_commands.describe(money="Количество обычных реверсивок для обмена")
    @app_commands.check(AbstractCog.reconnect)  # noqa
    @profile_check()
    async def swap(self, interaction: discord.Interaction, money: int):
        ctx: Context = await self.client.get_context(interaction)
        await ctx.supplement()
        user = UserDiscord.get(UserDiscord.discord_id == ctx.author.id)

        if user.money < money:
            await ctx.send(embed=await ctx.embed_message("Недостаточно реверсивок.",
                                                         "Вы хотите обменять реверсивки, которых у "
                                                         "Вас меньше, чем вы ввели."))
            return

        user.money -= money
        user.gold_money = user.gold_money + (money // 4)
        user.save()

        await interaction.response.send_message(
            embed=await ctx.embed_message("Реверсивки успешно обменены.",
                                          f"Вы обменяли {money} реверсивок на {int(money / 4)} золотых реверсивок"))

    @app_commands.command(name="выбор",
                          description="Команда создает голосование, которое можно использовать как угодно.")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def polls(self, interaction: discord.Interaction, ):
        await interaction.response.send_modal(ModalChoice())


async def setup(client):
    await client.add_cog(MainCommands(client))
