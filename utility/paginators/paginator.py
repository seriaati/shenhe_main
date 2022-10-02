__all__ = ["GeneralPaginator"]


from io import BytesIO
from typing import List, Optional, Union

import aiosqlite
from discord import ButtonStyle, Embed, File, Interaction, User
from discord.ui import Button, Select, button, View


class _view(View):
    def __init__(
        self,
        author: User,
        embeds: List[Embed],
        db: aiosqlite.Connection,
        check: bool = True,
        files: Optional[List[BytesIO]] = [],
    ):
        super().__init__(timeout=500)
        self.author = author
        self.embeds = embeds
        self.check = check
        self.files = files

        self.current_page = 0

    async def interaction_check(self, i: Interaction) -> bool:
        return i.user.id == self.author.id

    async def update_children(self, interaction: Interaction):
        self.next.disabled = self.current_page + 1 == len(self.embeds)
        self.previous.disabled = self.current_page <= 0

        kwargs = {"embed": self.embeds[self.current_page]}
        if len(self.files) > 0:
            fp = self.files[self.current_page]
            fp.seek(0)
            file_name = f"{self.current_page}.jpeg"
            file = File(fp, file_name)
            kwargs["attachments"] = [file]

        kwargs["view"] = self

        await interaction.response.edit_message(**kwargs)

    @button(
        emoji="<:double_left:982588991461281833>",
        style=ButtonStyle.gray,
        row=1,
        custom_id="paginator_double_left",
    )
    async def first(self, interaction: Interaction, button: Button):
        self.current_page = 0

        await self.update_children(interaction)

    @button(
        emoji="<:left:982588994778972171>",
        style=ButtonStyle.blurple,
        row=1,
        custom_id="paginator_left",
    )
    async def previous(self, interaction: Interaction, button: Button):
        self.current_page -= 1

        await self.update_children(interaction)

    @button(
        emoji="<:right:982588993122238524>",
        style=ButtonStyle.blurple,
        row=1,
        custom_id="paginator_right",
    )
    async def next(self, interaction: Interaction, button: Button):
        self.current_page += 1

        await self.update_children(interaction)

    @button(
        emoji="<:double_right:982588990223958047>",
        style=ButtonStyle.gray,
        row=1,
        custom_id="paginator_double_right",
    )
    async def last(self, interaction: Interaction, button: Button):
        self.current_page = len(self.embeds) - 1

        await self.update_children(interaction)


class GeneralPaginator:
    def __init__(
        self,
        interaction: Interaction,
        embeds: List[Embed],
        custom_children: Optional[List[Union[Button, Select]]] = [],
        files: Optional[List[BytesIO]] = [],
    ):
        self.custom_children = custom_children
        self.interaction = interaction
        self.embeds = embeds
        self.files = files

    async def start(
        self,
        edit: bool = False,
        followup: bool = False,
        check: bool = True,
        ephemeral: bool = False,
        dm: bool = False
    ) -> None:
        if not (self.embeds):
            raise ValueError("Missing embeds")

        view = _view(self.interaction.user, self.embeds, check, self.files)
        view.previous.disabled = True if (view.current_page <= 0) else False
        view.next.disabled = (
            True if (view.current_page + 1 >= len(self.embeds)) else False
        )

        if len(self.custom_children) > 0:
            for child in self.custom_children:
                view.add_item(child)

        kwargs = {"embed": self.embeds[view.current_page]}
        if len(self.files) > 0:
            fp = self.files[view.current_page]
            fp.seek(0)
            file_name = f"{view.current_page}.jpeg"
            file = File(fp, file_name)
            kwargs["files"] = [file]

        kwargs["view"] = view

        if not edit:
            kwargs["ephemeral"] = ephemeral

        if edit:
            if "files" in kwargs:
                del kwargs["files"]
                fp = self.files[view.current_page]
                fp.seek(0)
                file = File(fp, f"{view.current_page}.jpeg")
                kwargs["attachments"] = [file]

            await self.interaction.edit_original_response(**kwargs)
        elif followup:
            await self.interaction.followup.send(**kwargs)
        elif dm:
            del kwargs["ephemeral"]
            await self.interaction.user.send(**kwargs)
        else:
            await self.interaction.response.send_message(**kwargs)

        await view.wait()
