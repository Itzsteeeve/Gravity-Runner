from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from typing import Optional, Set

import pygame

from src.config import (
    FPS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    PLAYER_RADIUS,
    PLAYER_X,
    FLIP_COOLDOWN_S,
    START_SPEED_PX_S,
    MAX_SPEED_PX_S,
    SCORE_DIVISOR_PX,
    TITLE,
)
from src.game_state import GamePhase
from src.level_generator import LevelGenerator
from src.particles import ParticleSystem
from src.player import Player
from src.ui import (
    create_fonts,
    draw_background,
    draw_game_over,
    draw_hud,
    draw_menu,
    draw_pause_menu,
    MenuSection,
    MenuSettingsView,
    MenuSkinItemView,
    MenuView,
)
from src.audio import SfxBank
from src.skins import SKINS, default_skin_id, skins_by_id
from src.utils import (
    clamp,
    difficulty_from_progress,
    load_highscore,
    load_profile,
    resource_path,
    save_highscore,
    save_profile,
)


@dataclass
class ScreenScale:
    scale: float
    offset_x: int
    offset_y: int


def compute_scale(window_w: int, window_h: int) -> ScreenScale:
    ww = max(1, int(window_w))
    hh = max(1, int(window_h))
    s = max(0.001, min(ww / LOGICAL_WIDTH, hh / LOGICAL_HEIGHT))
    new_w = int(LOGICAL_WIDTH * s)
    new_h = int(LOGICAL_HEIGHT * s)
    off_x = (ww - new_w) // 2
    off_y = (hh - new_h) // 2
    return ScreenScale(scale=s, offset_x=off_x, offset_y=off_y)


def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    tt = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * tt),
        int(a[1] + (b[1] - a[1]) * tt),
        int(a[2] + (b[2] - a[2]) * tt),
    )


MENU_ROW_Y0 = 360
MENU_ROW_H = 48
MENU_TRANSITION_S = 0.18
MENU_CLICK_LEFT = LOGICAL_WIDTH // 2 - 250
MENU_CLICK_RIGHT = LOGICAL_WIDTH // 2 + 250
MENU_CLICK_TOP_PAD = 14
MENU_CLICK_BOTTOM_PAD = 30


class GravityRunner:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)

        # Logical rendering surface for consistent gameplay.
        self.logical_surface = pygame.Surface(
            (LOGICAL_WIDTH, LOGICAL_HEIGHT),
            pygame.SRCALPHA,
        )

        # Resizable window for a nicer UX.
        self.window = pygame.display.set_mode((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.fonts = create_fonts()
        self.particles = ParticleSystem()
        self.player = Player(x=float(PLAYER_X), y=LOGICAL_HEIGHT / 2.0)

        self.phase = GamePhase.menu
        self.seed = 1337
        # Difficulty (menu selection affects both speed & obstacle tempo).
        self.difficulty_mode = "normal"  # "easy" | "normal" | "hard"
        self._difficulty_multipliers = {"easy": 0.78, "normal": 1.0, "hard": 1.22}
        self._score_multipliers = {"easy": 1, "normal": 2, "hard": 3}

        # Profile-backed progression & settings.
        profile = load_profile()
        self.credits = int(profile.get("credits", 0))

        self.owned_skin_ids: Set[str] = set(profile.get("owned_skin_ids", [default_skin_id()]))
        self.equipped_skin_id = str(profile.get("equipped_skin_id", default_skin_id()))
        if self.equipped_skin_id not in self.owned_skin_ids:
            self.equipped_skin_id = default_skin_id()
            self.owned_skin_ids.add(self.equipped_skin_id)

        self.sound_enabled = bool(profile.get("settings", {}).get("sound_enabled", True))
        self.sfx_volume = float(profile.get("settings", {}).get("sfx_volume", 0.7))
        self.sfx_volume = clamp(self.sfx_volume, 0.0, 1.0)
        self.fx_intensity = float(profile.get("settings", {}).get("fx_intensity", 1.0))
        self.fx_intensity = clamp(self.fx_intensity, 0.0, 2.0)

        # Menu-only background music (try multiple locations for source/build parity).
        self.menu_music_path = ""
        self.menu_music_candidates = [
            resource_path(os.path.join("assets", "menu_music.mp3")),
            os.path.join(os.path.dirname(__file__), "assets", "menu_music.mp3"),
        ]
        self.menu_music_fallback_candidates = [
            "/home/stepan/Stažené/dejcomin-deep-ambient-electronic-theme-music-loading-screen-menu-dejcoart-429846.mp3",
        ]
        self.menu_music_ready = False
        self.menu_music_playing = False

        # Resolve active skin theme.
        skin_defs = skins_by_id()
        self.active_skin_id = self.equipped_skin_id
        self.active_skin_theme = skin_defs.get(self.active_skin_id, skin_defs[default_skin_id()]).theme

        # Menu state (animated, navigable).
        self.menu_section = MenuSection.MAIN
        self.menu_prev_section: Optional[MenuSection] = None
        self.menu_transition_progress = 0.0
        self.menu_main_selected = 0
        self.menu_difficulty_selected = 1
        self.menu_settings_selected = 0
        self.menu_skins_selected = 0
        self.menu_skins_scroll = 0
        self.menu_skins_visible_rows = 4
        self.menu_cursor_y = float(MENU_ROW_Y0 + self.menu_main_selected * MENU_ROW_H)
        self.menu_message: Optional[str] = None
        self.menu_message_timer = 0.0
        self.menu_preview_timer = 0.0
        self.menu_preview_flip_timer = 0.0
        self.menu_preview_target_y = float(LOGICAL_HEIGHT * 0.5)

        # Double-W detection for flip (running phase only).
        self._w_last_down_s: Optional[float] = None
        self._w_double_window_s = 0.25

        # Pause menu
        self.pause_selected = 0
        self.pause_cursor_y = float(MENU_ROW_Y0)

        # Audio bank (procedural SFX).
        self.sfx: Optional[SfxBank] = None
        if self.sound_enabled:
            try:
                self.sfx = SfxBank.create()
            except Exception:
                self.sound_enabled = False
                self.sfx = None
        self._init_menu_music()
        self._sync_menu_music()

        # Running state
        self.distance = 0.0
        self.speed_px_s = START_SPEED_PX_S
        self.score = 0
        self.click_score_base = 0
        self.highscore = load_highscore()

        self.generator = LevelGenerator.create(
            self.seed,
            self.active_skin_theme,
            self._difficulty_multipliers[self.difficulty_mode],
            self.difficulty_mode,
        )

        self._try_load_optional_assets()

        # Timing & effects
        self.flip_cooldown = 0.0
        self.death_timer = 0.0
        self.flip_flash_timer = 0.0
        self.flip_flash_duration = 0.18
        self.gravity_blend_timer = 0.0
        self.gravity_blend_duration = 0.20
        self.prev_gravity_sign = self.player.gravity_sign
        self.screen_shake_timer = 0.0
        self.screen_shake_strength = 0.0

        # Boundaries (player collisions)
        self.ceiling_y = 80
        self.floor_y = LOGICAL_HEIGHT - 80

        # Input
        self._flip_held_prevent = False

    def reset_run(self) -> None:
        self.distance = 0.0
        self.speed_px_s = START_SPEED_PX_S
        self.score = 0
        self.click_score_base = 0
        self.flip_cooldown = 0.0
        self.death_timer = 0.0
        self.flip_flash_timer = 0.0
        self.gravity_blend_timer = 0.0
        self.prev_gravity_sign = self.player.gravity_sign
        self.screen_shake_timer = 0.0
        self.screen_shake_strength = 0.0
        self.particles = ParticleSystem()
        self.player.reset(x=float(PLAYER_X), y=LOGICAL_HEIGHT / 2.0)
        self.generator = LevelGenerator.create(
            self.seed,
            self.active_skin_theme,
            self._difficulty_multipliers[self.difficulty_mode],
            self.difficulty_mode,
        )
        self.phase = GamePhase.running

    def _set_menu_message(self, text: str, duration_s: float = 1.2) -> None:
        self.menu_message = text
        self.menu_message_timer = duration_s

    def _init_menu_music(self) -> None:
        if not self.sound_enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            # Build candidate list: configured paths + recursive scan inside _MEIPASS.
            load_candidates = list(self.menu_music_candidates)
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass and os.path.isdir(meipass):
                for root, _dirs, files in os.walk(meipass):
                    for fn in files:
                        low = fn.lower()
                        if low.endswith(".mp3") or low.endswith(".ogg") or low.endswith(".wav"):
                            load_candidates.append(os.path.join(root, fn))
            # Only after bundled attempts fail, try local-machine fallback paths.
            load_candidates.extend(self.menu_music_fallback_candidates)

            # Deduplicate while preserving order.
            dedup: list[str] = []
            seen = set()
            for c in load_candidates:
                if c in seen:
                    continue
                seen.add(c)
                dedup.append(c)

            for candidate in dedup:
                try:
                    if not os.path.exists(candidate):
                        continue
                    pygame.mixer.music.load(candidate)
                    pygame.mixer.music.set_volume(self.sfx_volume * 0.55)
                    self.menu_music_path = candidate
                    self.menu_music_ready = True
                    return
                except Exception:
                    continue

            self.menu_music_ready = False
        except Exception:
            self.menu_music_ready = False
            self.menu_music_playing = False

    def _sync_menu_music(self) -> None:
        want_menu_music = self.sound_enabled and self.menu_music_ready and self.phase == GamePhase.menu
        try:
            if want_menu_music and not self.menu_music_playing:
                pygame.mixer.music.set_volume(self.sfx_volume * 0.55)
                pygame.mixer.music.play(-1)
                self.menu_music_playing = True
            elif (not want_menu_music) and self.menu_music_playing:
                pygame.mixer.music.stop()
                self.menu_music_playing = False
        except Exception:
            self.menu_music_playing = False

    def _enter_main_menu(self) -> None:
        self.phase = GamePhase.menu
        self._switch_menu_section(MenuSection.MAIN)
        self.menu_prev_section = None
        self.menu_transition_progress = 1.0
        self.menu_cursor_y = float(MENU_ROW_Y0 + self.menu_main_selected * MENU_ROW_H)
        self._sync_menu_music()

    def _window_to_logical(self, x_win: int, y_win: int) -> Optional[tuple[int, int]]:
        win_w, win_h = self.window.get_size()
        sc = compute_scale(win_w, win_h)
        render_w = int(LOGICAL_WIDTH * sc.scale)
        render_h = int(LOGICAL_HEIGHT * sc.scale)
        local_x = x_win - sc.offset_x
        local_y = y_win - sc.offset_y
        if local_x < 0 or local_y < 0 or local_x >= render_w or local_y >= render_h:
            return None
        if sc.scale <= 0:
            return None
        lx = int(local_x / sc.scale)
        ly = int(local_y / sc.scale)
        return lx, ly

    def _menu_row_count(self) -> int:
        if self.menu_section == MenuSection.MAIN:
            return 5
        if self.menu_section == MenuSection.DIFFICULTY:
            return 4
        if self.menu_section == MenuSection.SETTINGS:
            return 4
        return len(SKINS) + 1

    def _menu_skins_scroll_limits(self) -> tuple[int, int]:
        total = len(SKINS) + 1
        visible = max(3, self.menu_skins_visible_rows)
        return visible, max(0, total - visible)

    def _ensure_skins_selection_visible(self) -> None:
        if self.menu_section != MenuSection.SKINS:
            return
        visible, max_scroll = self._menu_skins_scroll_limits()
        self.menu_skins_scroll = int(clamp(self.menu_skins_scroll, 0, max_scroll))
        if self.menu_skins_selected < self.menu_skins_scroll:
            self.menu_skins_scroll = self.menu_skins_selected
        elif self.menu_skins_selected >= self.menu_skins_scroll + visible:
            self.menu_skins_scroll = self.menu_skins_selected - visible + 1
        self.menu_skins_scroll = int(clamp(self.menu_skins_scroll, 0, max_scroll))

    def _menu_select_index(self, idx: int) -> None:
        n = self._menu_row_count()
        if n <= 0:
            return
        i = int(clamp(idx, 0, n - 1))
        if self.menu_section == MenuSection.MAIN:
            self.menu_main_selected = i
        elif self.menu_section == MenuSection.DIFFICULTY:
            self.menu_difficulty_selected = i
        elif self.menu_section == MenuSection.SETTINGS:
            self.menu_settings_selected = i
        else:
            self.menu_skins_selected = i

    def _handle_menu_click(self, lx: int, ly: int) -> bool:
        if self.menu_section == MenuSection.SKINS:
            list_x = LOGICAL_WIDTH // 2 - 340
            list_y0 = 360
            list_w = 290
            list_h = 44
            list_gap = 8
            total = len(SKINS) + 1
            visible, max_scroll = self._menu_skins_scroll_limits()
            self.menu_skins_scroll = int(clamp(self.menu_skins_scroll, 0, max_scroll))
            if list_x <= lx <= (list_x + list_w):
                for vis_i in range(visible):
                    i = self.menu_skins_scroll + vis_i
                    if i >= total:
                        break
                    y = list_y0 + vis_i * (list_h + list_gap)
                    if y <= ly <= (y + list_h):
                        self._menu_select_index(i)
                        self._ensure_skins_selection_visible()
                        self._menu_confirm()
                        return True
            return False

        if MENU_CLICK_LEFT <= lx <= MENU_CLICK_RIGHT:
            row_count = self._menu_row_count()
            for i in range(row_count):
                y = MENU_ROW_Y0 + i * MENU_ROW_H
                if (y - MENU_CLICK_TOP_PAD) <= ly <= (y + MENU_CLICK_BOTTOM_PAD):
                    self._menu_select_index(i)
                    self._menu_confirm()
                    return True
        return False

    def _handle_pause_click(self, lx: int, ly: int) -> bool:
        if lx < MENU_CLICK_LEFT or lx > MENU_CLICK_RIGHT:
            return False
        for i in range(2):
            y = MENU_ROW_Y0 + i * MENU_ROW_H
            if (y - MENU_CLICK_TOP_PAD) <= ly <= (y + MENU_CLICK_BOTTOM_PAD):
                self.pause_selected = i
                if i == 0:
                    self.phase = GamePhase.running
                else:
                    self._enter_main_menu()
                self._sync_menu_music()
                return True
        return False

    def _switch_menu_section(self, new_section: MenuSection) -> None:
        if new_section == self.menu_section:
            return
        self.menu_prev_section = self.menu_section
        self.menu_section = new_section
        self.menu_transition_progress = 0.0

    def _open_menu_difficulty(self) -> None:
        self.menu_difficulty_selected = {"easy": 0, "normal": 1, "hard": 2}.get(self.difficulty_mode, 1)
        self._switch_menu_section(MenuSection.DIFFICULTY)

    def _open_menu_settings(self) -> None:
        self._switch_menu_section(MenuSection.SETTINGS)

    def _open_menu_skins(self) -> None:
        idx = next((i for i, s in enumerate(SKINS) if s.id == self.equipped_skin_id), 0)
        self.menu_skins_selected = idx
        visible, max_scroll = self._menu_skins_scroll_limits()
        self.menu_skins_scroll = int(clamp(idx - 1, 0, max_scroll))
        self._switch_menu_section(MenuSection.SKINS)

    def _menu_confirm(self) -> None:
        # Handles ENTER in menu.
        if self.menu_section == MenuSection.MAIN:
            if self.menu_main_selected == 0:
                self.reset_run()
                return
            if self.menu_main_selected == 1:
                self._open_menu_difficulty()
                return
            if self.menu_main_selected == 2:
                self._open_menu_settings()
                return
            if self.menu_main_selected == 3:
                self._open_menu_skins()
                return
            # EXIT
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        if self.menu_section == MenuSection.DIFFICULTY:
            # 0..2: select difficulty, 3: back
            if 0 <= self.menu_difficulty_selected <= 2:
                self.difficulty_mode = {0: "easy", 1: "normal", 2: "hard"}.get(self.menu_difficulty_selected, "normal")
                self._switch_menu_section(MenuSection.MAIN)
            else:
                self._switch_menu_section(MenuSection.MAIN)
            return

        if self.menu_section == MenuSection.SETTINGS:
            # 0 sound toggle, 1..2 cycles, 3 back
            if self.menu_settings_selected == 0:
                self.sound_enabled = not self.sound_enabled
                if self.sound_enabled:
                    try:
                        self.sfx = SfxBank.create()
                    except Exception:
                        self.sound_enabled = False
                        self.sfx = None
                        self._set_menu_message("Sound not available on this system.")
                else:
                    self.sfx = None
                    self._set_menu_message("Sound OFF", duration_s=0.8)
            elif self.menu_settings_selected == 1:
                steps = [0.0, 0.25, 0.5, 0.75, 1.0]
                cur_idx = min(range(len(steps)), key=lambda i: abs(steps[i] - self.sfx_volume))
                self.sfx_volume = steps[(cur_idx + 1) % len(steps)]
            elif self.menu_settings_selected == 2:
                steps2 = [0.4, 0.7, 1.0, 1.3, 1.6]
                cur_idx = min(range(len(steps2)), key=lambda i: abs(steps2[i] - self.fx_intensity))
                self.fx_intensity = steps2[(cur_idx + 1) % len(steps2)]
            else:
                self._switch_menu_section(MenuSection.MAIN)

            # Persist settings changes.
            profile = load_profile()
            profile["owned_skin_ids"] = list(sorted(self.owned_skin_ids))
            profile["equipped_skin_id"] = self.equipped_skin_id
            profile["credits"] = int(self.credits)
            profile["settings"] = {
                "sound_enabled": self.sound_enabled,
                "sfx_volume": self.sfx_volume,
                "fx_intensity": self.fx_intensity,
            }
            save_profile(profile)
            if self.sound_enabled and not self.menu_music_ready:
                self._init_menu_music()
            self._sync_menu_music()
            return

        if self.menu_section == MenuSection.SKINS:
            back_idx = len(SKINS)
            if self.menu_skins_selected == back_idx:
                self._switch_menu_section(MenuSection.MAIN)
                return

            skin_def = SKINS[self.menu_skins_selected]
            if skin_def.id in self.owned_skin_ids:
                self.equipped_skin_id = skin_def.id
                self.active_skin_id = skin_def.id
                self.active_skin_theme = skin_def.theme
                # Persist equip change.
                profile = load_profile()
                profile["credits"] = int(self.credits)
                profile["owned_skin_ids"] = list(sorted(self.owned_skin_ids))
                profile["equipped_skin_id"] = self.equipped_skin_id
                profile["settings"] = {
                    "sound_enabled": self.sound_enabled,
                    "sfx_volume": self.sfx_volume,
                    "fx_intensity": self.fx_intensity,
                }
                save_profile(profile)
                self._set_menu_message("Equipped!", duration_s=0.8)
                return

            # Purchase flow
            if self.credits < skin_def.price_credits:
                self._set_menu_message("Not enough credits.")
                return

            self.credits -= skin_def.price_credits
            self.owned_skin_ids.add(skin_def.id)
            self.equipped_skin_id = skin_def.id
            self.active_skin_id = skin_def.id
            self.active_skin_theme = skin_def.theme

            profile = load_profile()
            profile["credits"] = int(self.credits)
            profile["owned_skin_ids"] = list(sorted(self.owned_skin_ids))
            profile["equipped_skin_id"] = self.equipped_skin_id
            profile["settings"] = {
                "sound_enabled": self.sound_enabled,
                "sfx_volume": self.sfx_volume,
                "fx_intensity": self.fx_intensity,
            }
            save_profile(profile)
            self._set_menu_message("Skin purchased!", duration_s=0.9)
            return

    def _try_load_optional_assets(self) -> None:
        """
        Optional asset loading.
        This is mainly here so the PyInstaller build can include `assets/` and the code
        demonstrates correct path resolution via `resource_path()`.
        """
        try:
            icon_path = resource_path(os.path.join("assets", "icon.png"))
            if os.path.exists(icon_path):
                icon = pygame.image.load(icon_path)
                pygame.display.set_icon(icon)
        except Exception:
            # Assets are optional; ignore loading errors to keep gameplay runnable.
            return

    def _trigger_death(self) -> None:
        self.death_timer = 0.9
        self.phase = GamePhase.game_over

        # Update highscore.
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)

        # Death particles near the player.
        self.particles.emit_death(self.player.x, self.player.y, self.active_skin_theme.player_up)

        # Credits progression (shop currency).
        self.credits = max(0, int(self.credits + max(0, self.score)))
        profile = load_profile()
        # Merge with current in-memory changes, then persist.
        profile["credits"] = self.credits
        profile["owned_skin_ids"] = list(sorted(self.owned_skin_ids))
        profile["equipped_skin_id"] = self.equipped_skin_id
        profile["settings"] = {
            "sound_enabled": self.sound_enabled,
            "sfx_volume": self.sfx_volume,
            "fx_intensity": self.fx_intensity,
        }
        save_profile(profile)

        if self.sound_enabled and self.sfx is not None:
            try:
                self.sfx.play_death(self.sfx_volume)
            except Exception:
                pass

        # Screen shake for punch.
        self.screen_shake_timer = 0.6
        self.screen_shake_strength = 10.0 * self.fx_intensity

    def _flip(self) -> None:
        self._w_last_down_s = None
        self.prev_gravity_sign = self.player.gravity_sign
        self.player.flip_gravity()
        self.flip_cooldown = FLIP_COOLDOWN_S
        self.flip_flash_timer = self.flip_flash_duration
        self.gravity_blend_timer = self.gravity_blend_duration
        self.screen_shake_timer = 0.10
        self.screen_shake_strength = 3.0 * self.fx_intensity
        self.particles.emit_flip(self.player.x, self.player.y, self.active_skin_theme.accent)

        if self.sound_enabled and self.sfx is not None:
            try:
                self.sfx.play_flip(self.sfx_volume)
            except Exception:
                pass

    def update(self, dt: float) -> None:
        # Global timers.
        if self.flip_cooldown > 0:
            self.flip_cooldown = max(0.0, self.flip_cooldown - dt)
        if self.flip_flash_timer > 0:
            self.flip_flash_timer = max(0.0, self.flip_flash_timer - dt)
        if self.gravity_blend_timer > 0:
            self.gravity_blend_timer = max(0.0, self.gravity_blend_timer - dt)

        # Screen shake.
        if self.screen_shake_timer > 0:
            self.screen_shake_timer = max(0.0, self.screen_shake_timer - dt)

        if self.phase == GamePhase.running:
            progress = max(0.0, self.distance / 22000.0) * self._difficulty_multipliers[self.difficulty_mode]
            diff = difficulty_from_progress(progress)
            self.speed_px_s = clamp(diff.speed_px_s, START_SPEED_PX_S, MAX_SPEED_PX_S)

            # Move camera.
            self.distance += self.speed_px_s * dt
            base_run_score = int(self.distance / SCORE_DIVISOR_PX) + self.click_score_base
            mult = self._score_multipliers.get(self.difficulty_mode, 1)
            self.score = base_run_score * mult

            # Update player physics.
            self.player.update(dt, ceiling_y=self.ceiling_y, floor_y=self.floor_y)

            # Spawn/maintain obstacles.
            self.generator.update(camera_x=self.distance, ceiling_y=self.ceiling_y, floor_y=self.floor_y)

            # Collisions with gates.
            for g in self.generator.gates:
                if g.collides_circle(
                    player_x_screen=self.player.x,
                    player_y_screen=self.player.y,
                    player_radius=PLAYER_RADIUS,
                    camera_x=self.distance,
                ):
                    self._trigger_death()
                    return

        elif self.phase == GamePhase.game_over:
            # Death effect progression (freeze gameplay feel).
            self.death_timer -= dt
            if self.death_timer <= 0.0:
                self.reset_run()

        elif self.phase == GamePhase.menu:
            # Menu transition (slide + fade).
            if self.menu_prev_section is not None:
                self.menu_transition_progress = min(1.0, self.menu_transition_progress + dt / MENU_TRANSITION_S)
                if self.menu_transition_progress >= 1.0:
                    self.menu_prev_section = None

            # Cursor animation toward the selected row in the current section.
            if self.menu_section == MenuSection.MAIN:
                selected_idx = self.menu_main_selected
                target_y = MENU_ROW_Y0 + selected_idx * MENU_ROW_H
            elif self.menu_section == MenuSection.DIFFICULTY:
                selected_idx = self.menu_difficulty_selected
                target_y = MENU_ROW_Y0 + selected_idx * MENU_ROW_H
            elif self.menu_section == MenuSection.SETTINGS:
                selected_idx = self.menu_settings_selected
                target_y = MENU_ROW_Y0 + selected_idx * MENU_ROW_H
            else:
                selected_idx = self.menu_skins_selected
                vis_i = max(0, selected_idx - self.menu_skins_scroll)
                target_y = 360 + vis_i * (44 + 8)
            # Exponential smoothing, framerate-independent.
            k = 1.0 - math.exp(-dt * 16.0)
            self.menu_cursor_y = self.menu_cursor_y + (target_y - self.menu_cursor_y) * k

            # Message lifecycle.
            if self.menu_message_timer > 0.0:
                self.menu_message_timer = max(0.0, self.menu_message_timer - dt)
                if self.menu_message_timer <= 0.0:
                    self.menu_message = None

        elif self.phase == GamePhase.paused:
            # Pause cursor smoothing.
            target = MENU_ROW_Y0 + self.pause_selected * MENU_ROW_H
            k = 1.0 - math.exp(-dt * 16.0)
            self.pause_cursor_y = self.pause_cursor_y + (target - self.pause_cursor_y) * k

        self.particles.update(dt)
        self._sync_menu_music()

    def draw_player(self, surf: pygame.Surface) -> None:
        # Neon circle with glow layers.
        x = int(self.player.x)
        y = int(self.player.y)
        r = int(PLAYER_RADIUS)
        gravity_down = self.player.gravity_sign > 0
        target_base = self.active_skin_theme.player_down if gravity_down else self.active_skin_theme.player_up
        if self.prev_gravity_sign > 0:
            prev_base = self.active_skin_theme.player_down
        else:
            prev_base = self.active_skin_theme.player_up

        if self.gravity_blend_timer > 0 and self.gravity_blend_duration > 0:
            p = 1.0 - (self.gravity_blend_timer / self.gravity_blend_duration)
            # Smoothstep easing for less abrupt visual switching.
            p = p * p * (3.0 - 2.0 * p)
            base = lerp_color(prev_base, target_base, p)
        else:
            base = target_base

        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for rr, a in [(r + 14, 55), (r + 9, 85), (r + 4, 120)]:
            pygame.draw.circle(overlay, (*base, a), (x, y), rr)
        surf.blit(overlay, (0, 0))

        pygame.draw.circle(surf, base, (x, y), r)
        pygame.draw.circle(surf, self.active_skin_theme.accent, (x, y), r - 5, width=2)

    def render(self) -> None:
        # Determine shake offset in logical space.
        shake_x = 0
        shake_y = 0
        if self.screen_shake_timer > 0:
            t = self.screen_shake_timer
            # Random-ish deterministic shake using sin; avoids importing random every frame.
            shake_x = int(math.sin(t * 55.0) * self.screen_shake_strength)
            shake_y = int(math.cos(t * 43.0) * self.screen_shake_strength)

        # Draw to logical surface.
        time_s = pygame.time.get_ticks() / 1000.0
        draw_background(self.logical_surface, time_s)

        # Obstacles & world.
        if self.phase != GamePhase.menu:
            for g in self.generator.gates:
                g.draw(
                    self.logical_surface,
                    camera_x=self.distance,
                    floor_y=self.floor_y,
                    ceiling_y=self.ceiling_y,
                )

        if self.phase in (GamePhase.running, GamePhase.game_over):
            self.draw_player(self.logical_surface)

        # Particles on top.
        self.particles.draw(self.logical_surface)

        # Flip shockwave.
        if self.flip_flash_timer > 0:
            t = self.flip_flash_timer
            d = self.flip_flash_duration
            # Expand with ease-out, then fade.
            p = 1.0 - (t / d) if d > 0 else 1.0
            ease_out = 1.0 - ((1.0 - p) ** 3)
            radius = int(18 + 72 * ease_out)
            alpha = int(220 * (1.0 - p) * (1.0 - p))
            col = self.active_skin_theme.accent
            overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(overlay, (*col, alpha), (int(self.player.x), int(self.player.y)), radius, width=3)
            self.logical_surface.blit(overlay, (0, 0))

        # UI by phase.
        if self.phase == GamePhase.menu:
            skin_items: list[MenuSkinItemView] = [
                MenuSkinItemView(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    price_credits=s.price_credits,
                    owned=(s.id in self.owned_skin_ids),
                    equipped=(s.id == self.equipped_skin_id),
                    preview_player_down=s.theme.player_down,
                    preview_player_up=s.theme.player_up,
                    preview_accent=s.theme.accent,
                    preview_gate_wall=s.theme.gate_wall,
                    preview_gate_outline=s.theme.gate_outline,
                    preview_spike=s.theme.spike_a,
                )
                for s in SKINS
            ]

            settings_view = MenuSettingsView(
                sound_enabled=self.sound_enabled,
                sfx_volume=self.sfx_volume,
                fx_intensity=self.fx_intensity,
            )

            view = MenuView(
                section=self.menu_section,
                prev_section=self.menu_prev_section,
                transition_progress=self.menu_transition_progress,
                cursor_y=self.menu_cursor_y,
                main_selected=self.menu_main_selected,
                difficulty_selected=self.menu_difficulty_selected,
                settings_selected=self.menu_settings_selected,
                skins_selected=self.menu_skins_selected,
                skins_scroll=self.menu_skins_scroll,
                skins_visible_rows=self.menu_skins_visible_rows,
                difficulty_mode_label=self.difficulty_mode.upper(),
                credits=self.credits,
                score=self.score,
                highscore=self.highscore,
                skin_items=skin_items,
                settings=settings_view,
                message=self.menu_message,
            )
            draw_menu(self.logical_surface, self.fonts, view)
        elif self.phase == GamePhase.running:
            draw_hud(
                self.logical_surface,
                self.fonts,
                score=self.score,
                highscore=self.highscore,
                phase_name="running",
                gravity_down=self.player.gravity_sign > 0,
                difficulty_label=self.difficulty_mode.upper(),
                score_multiplier=self._score_multipliers.get(self.difficulty_mode, 1),
                credits=self.credits,
            )
        elif self.phase == GamePhase.game_over:
            remaining = max(0.0, self.death_timer)
            # Dim overlay.
            overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
            alpha = int(160 * (remaining / 0.9))
            overlay.fill((*self.active_skin_theme.player_up, alpha))
            self.logical_surface.blit(overlay, (0, 0))

            draw_game_over(
                self.logical_surface,
                self.fonts,
                score=self.score,
                highscore=self.highscore,
                remaining_s=remaining,
            )
        elif self.phase == GamePhase.paused:
            draw_pause_menu(
                self.logical_surface,
                self.fonts,
                selected_index=self.pause_selected,
                cursor_y=self.pause_cursor_y,
            )

        # Scale to window.
        win_w, win_h = self.window.get_size()
        sc = compute_scale(win_w, win_h)
        scaled = pygame.transform.smoothscale(
            self.logical_surface,
            (max(1, int(LOGICAL_WIDTH * sc.scale)), max(1, int(LOGICAL_HEIGHT * sc.scale))),
        )
        # Fill letterbox areas with a stretched backdrop to avoid black side bars.
        backdrop = pygame.transform.smoothscale(self.logical_surface, (win_w, win_h))
        self.window.blit(backdrop, (0, 0))
        self.window.blit(scaled, (sc.offset_x + shake_x, sc.offset_y + shake_y))
        pygame.display.flip()

    def run(self) -> None:
        try:
            running = True
            while running:
                dt = self.clock.tick(FPS) / 1000.0

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        continue

                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_ESCAPE,):
                            if self.phase == GamePhase.running:
                                self.phase = GamePhase.paused
                                self.pause_selected = 0
                                self.pause_cursor_y = float(MENU_ROW_Y0)
                            elif self.phase == GamePhase.paused:
                                self.phase = GamePhase.running
                            elif self.phase == GamePhase.game_over:
                                self._enter_main_menu()
                            elif self.menu_section != MenuSection.MAIN:
                                self._switch_menu_section(MenuSection.MAIN)
                            else:
                                running = False
                            continue

                        if self.phase == GamePhase.menu:
                            up_keys = (pygame.K_UP, pygame.K_w)
                            down_keys = (pygame.K_DOWN, pygame.K_s)
                            enter_keys = (pygame.K_RETURN, pygame.K_KP_ENTER)

                            if event.key in up_keys:
                                if self.menu_section == MenuSection.MAIN:
                                    self.menu_main_selected = (self.menu_main_selected - 1) % 5
                                elif self.menu_section == MenuSection.DIFFICULTY:
                                    self.menu_difficulty_selected = (self.menu_difficulty_selected - 1) % 4
                                elif self.menu_section == MenuSection.SETTINGS:
                                    self.menu_settings_selected = (self.menu_settings_selected - 1) % 4
                                else:
                                    total = len(SKINS) + 1
                                    self.menu_skins_selected = (self.menu_skins_selected - 1) % total
                                    self._ensure_skins_selection_visible()

                            elif event.key in down_keys:
                                if self.menu_section == MenuSection.MAIN:
                                    self.menu_main_selected = (self.menu_main_selected + 1) % 5
                                elif self.menu_section == MenuSection.DIFFICULTY:
                                    self.menu_difficulty_selected = (self.menu_difficulty_selected + 1) % 4
                                elif self.menu_section == MenuSection.SETTINGS:
                                    self.menu_settings_selected = (self.menu_settings_selected + 1) % 4
                                else:
                                    total = len(SKINS) + 1
                                    self.menu_skins_selected = (self.menu_skins_selected + 1) % total
                                    self._ensure_skins_selection_visible()

                            elif event.key in enter_keys:
                                self._menu_confirm()
                        elif self.phase == GamePhase.running:
                            if event.key == pygame.K_UP:
                                if self.flip_cooldown <= 0:
                                    self._flip()
                            elif event.key == pygame.K_w:
                                # Double W flip (within a small window).
                                if self.flip_cooldown <= 0:
                                    now_s = pygame.time.get_ticks() / 1000.0
                                    if self._w_last_down_s is None:
                                        self._w_last_down_s = now_s
                                    else:
                                        if now_s - self._w_last_down_s <= self._w_double_window_s:
                                            self._w_last_down_s = None
                                            self._flip()
                                        else:
                                            self._w_last_down_s = now_s
                                else:
                                    self._w_last_down_s = None
                            elif event.key == pygame.K_SPACE:
                                if self.flip_cooldown <= 0:
                                    self._flip()
                        elif self.phase == GamePhase.game_over:
                            if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                                self.reset_run()
                        elif self.phase == GamePhase.paused:
                            if event.key in (pygame.K_UP, pygame.K_w):
                                self.pause_selected = (self.pause_selected - 1) % 2
                            elif event.key in (pygame.K_DOWN, pygame.K_s):
                                self.pause_selected = (self.pause_selected + 1) % 2
                            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                                if self.pause_selected == 0:
                                    self.phase = GamePhase.running
                                else:
                                    self._enter_main_menu()

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        logical = self._window_to_logical(*event.pos)
                        if logical is None:
                            continue
                        lx, ly = logical

                        if self.phase == GamePhase.running and self.flip_cooldown <= 0:
                            # Click grants a tiny base score; final score is difficulty-multiplied.
                            self.click_score_base += 2
                            self._flip()
                        elif self.phase == GamePhase.menu:
                            self._handle_menu_click(lx, ly)
                        elif self.phase == GamePhase.paused:
                            self._handle_pause_click(lx, ly)

                    if event.type == pygame.MOUSEWHEEL and self.phase == GamePhase.menu and self.menu_section == MenuSection.SKINS:
                        # Mouse wheel scroll in shop list.
                        _, max_scroll = self._menu_skins_scroll_limits()
                        self.menu_skins_scroll = int(clamp(self.menu_skins_scroll - event.y, 0, max_scroll))
                        self._ensure_skins_selection_visible()
                self.update(dt)
                self.render()
        except Exception as e:
            # Fail gracefully with an on-screen message.
            print(f"Fatal error: {e}", file=sys.stderr)
            try:
                self.window.fill((0, 0, 0))
                msg = self._render_error(str(e))
                self.window.blit(msg, (20, 20))
                pygame.display.flip()
                pygame.time.wait(3500)
            except Exception:
                pass
        finally:
            pygame.quit()

    def _render_error(self, text: str) -> pygame.Surface:
        # Render a basic error overlay; keep it simple.
        surf = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        surf.fill((10, 10, 10))
        font = pygame.font.SysFont("DejaVu Sans Mono", 20, bold=True)
        t = font.render("Error: " + text[:240], True, (255, 80, 80))
        surf.blit(t, (20, 20))
        return surf


def main() -> None:
    GravityRunner().run()


if __name__ == "__main__":
    main()

