# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import traceback

import discord

from discord.ext import commands
from typing import TYPE_CHECKING, Optional, Union
from pymemcache.client.base import Client
from datetime import datetime

from utils.models import UserDiscord, GuildDiscord

if TYPE_CHECKING:
    from main import Katherine

# Cache client used to avoid a large number of
# database calls during a context call.
cache_client = Client(('127.0.0.1', 11211))

logger = logging.getLogger("root")


class NotFound(Exception):
    pass
 

class Context(commands.Context):
    bot: Katherine

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.logging = None
        self.df_role = None
        self.administrator_role = None
        self.op_role = None

    async def embed_message(self,
                            title: str = "",
                            text: str = "",
                            color: discord.Colour = discord.Colour.og_blurple(),
                            icon_url: str = "",
                            thumbnail: str = "",
                            image: str = "",
                            footer: str = "",
                            fields: list = None):

        if not title and not text:
            raise commands.ArgumentParsingError

        embed = discord.Embed(colour=color)

        if title:
            embed.set_author(name=title, icon_url=icon_url if icon_url else self.guild.icon)

        if text:
            embed.description = text

        if image:
            embed.set_image(url=image)

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        if fields:
            for field in fields:
                embed.add_field(name=field["title"],
                                value=field["text"],
                                inline=False)

        embed.set_footer(text=footer if footer else None,
                         icon_url=self.bot.user.avatar)

        embed.timestamp = datetime.now()

        return embed

    async def supplement(self):
        UserDiscord.insert(discord_id=self.author.id).on_conflict_ignore().execute()

        if not cache_client.get(str(self.guild.id)):
            values = dict()

            guild: GuildDiscord = GuildDiscord.get(GuildDiscord.guild == self.guild.id)

            if guild.log_channel:
                self.logging: discord.TextChannel = discord.utils.get(self.bot.get_all_channels(),
                                                                      id=int(guild.log_channel))
                values['logging_id'] = int(guild.log_channel)

            if guild.default_role:
                self.df_role: discord.Role = self.guild.get_role(int(guild.default_role))
                values['default_role_id'] = self.df_role.id
            else:
                self.df_role: discord.Role = self.guild.default_role
                values['default_role_id'] = self.df_role.id

            if guild.admin_role:
                self.administrator_role: discord.Role = self.guild.get_role(int(guild.admin_role))
                values['admin_role_id'] = self.administrator_role.id
            else:
                self.administrator_role: discord.Role = self.guild.roles[-1]
                values['admin_role_id'] = self.administrator_role.id

            if guild.operator_role:
                self.op_role: discord.Role = self.guild.get_role(int(guild.operator_role))
                values['operator_role_id'] = self.op_role.id

            cache_client.set(str(self.guild.id), values, expire=60 * 60)
        else:
            data: bytes = cache_client.get(str(self.guild.id))
            if data != b'{}':
                values: dict = eval(data)
                if 'logging_id' in values.keys():
                    self.logging: discord.TextChannel = discord.utils.get(self.bot.get_all_channels(),
                                                                          id=values['logging_id'])
                if 'default_role_id' in values.keys():
                    self.df_role: discord.Role = self.guild.get_role(values['default_role_id'])

                if 'admin_role_id' in values.keys():
                    self.administrator_role: discord.Role = self.guild.get_role(values['admin_role_id'])

                if 'operator_role_id' in values.keys():
                    self.op_role: discord.Role = self.guild.get_role(values['operator_role_id'])

    async def log_to_channel(self,
                             text: str = None,
                             embed: discord.Embed = None,
                             file: discord.File = None) -> Optional[Union[discord.Message, None]]:
        if not text and not embed:
            raise AttributeError("Not enough arguments in command")

        if self.logging:
            return await self.logging.send(content=text, embed=embed, file=file)
        else:
            return None

    @property
    def log_channel(self) -> Optional[Union[discord.TextChannel, None]]:
        return self.logging

    @property
    def default_role(self) -> Optional[Union[discord.Role, None]]:
        return self.df_role

    @property
    def admin_role(self) -> Optional[Union[discord.Role, None]]:
        return self.administrator_role

    @property
    def operator_role(self) -> Optional[Union[discord.Role, None]]:
        return self.op_role

    @property
    def log(self):
        return logger
