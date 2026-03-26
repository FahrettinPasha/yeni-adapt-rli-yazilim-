# level_integration.py
import importlib
import pygame

def run_level(level_num: int, player_entity, level_args=None):
    """
    Belirtilen seviyeyi, ana oyunun PlayerEntity nesnesi ile başlatır.
    player_entity: PlayerEntity (health, stamina, combos, action_queue, update(dt, platforms), draw(surf, ox, oy) içerir)
    """
    try:
        module = importlib.import_module(f'level{level_num}')
    except ImportError as e:
        print(f"Level {level_num} yüklenemedi: {e}")
        return "error"

    if hasattr(module, 'main'):
        adapter = LevelPlayerAdapter(player_entity)
        module.main(external_player=adapter)
        return "done"
    else:
        print(f"Level {level_num} modülünde main() fonksiyonu yok.")
        return "error"


class LevelPlayerAdapter:
    """
    Ana oyunun PlayerEntity'sini, level dosyalarındaki basit Player arayüzüne uyarlar.
    Level'ın kullandığı tüm değerler (hp, dc, hc, ac, on, f, vx, vy) doğrudan ana karakterden okunur.
    Dash ve saldırı çağrıları, ana karakterin kendi sistemlerine yönlendirilir.
    """
    def __init__(self, main_player):
        self._main = main_player
        # Bileşenlere kısayollar (dökümandaki isimlerle)
        self._health = main_player.health          # HealthComponent
        self._stamina = main_player.stamina        # StaminaComponent
        self._combos = main_player.combos          # MeleeComboComponent

        # Level'ın kullandığı ek değişkenler (geçici, sadece animasyon/süre için)
        self.dt = 0.0          # dash timer (aktif dash süresi – level'ın dash animasyonu için)
        self.ac = 0.0          # attack cooldown (level'ın kendi saldırı cooldown'u)
        # NOT: hc ve dc artık property olarak ana karakterden okunuyor. Aşağıdaki property'lere bak.

        # Level'ın ihtiyaç duyduğu sabit boyut bilgileri (PlayerEntity'de olduğu varsayılır)
        self.W = main_player.width
        self.H = main_player.height
        self.HP = self._health.max_hp

        # Level'ın doğrudan eriştiği özellikler (property'ler ile yönlendirilir)
        self._rect = main_player.rect
        self._vx = main_player.vx
        self._vy = main_player.vy
        self._on = main_player.on_ground
        self._facing = main_player.facing
        self._alive = main_player.alive

    # ---- Property'ler (level'ın direkt okuma/yazma yapması için) ----
    @property
    def rect(self):
        return self._rect

    @rect.setter
    def rect(self, val):
        self._rect = val
        self._main.rect = val

    @property
    def vx(self):
        return self._vx

    @vx.setter
    def vx(self, val):
        self._vx = val
        self._main.vx = val

    @property
    def vy(self):
        return self._vy

    @vy.setter
    def vy(self, val):
        self._vy = val
        self._main.vy = val

    @property
    def on(self):
        return self._on

    @on.setter
    def on(self, val):
        self._on = val
        self._main.on_ground = val

    @property
    def f(self):
        return self._facing

    @f.setter
    def f(self, val):
        self._facing = val
        self._main.facing = val

    @property
    def hp(self):
        return self._health.hp

    @hp.setter
    def hp(self, val):
        self._health.hp = val
        if val <= 0:
            self._alive = False

    @property
    def alive(self):
        return self._alive

    @alive.setter
    def alive(self, val):
        self._alive = val
        self._main.alive = val

    @property
    def hc(self):
        """Level'ın beklediği hit cooldown (invincibility) – ana karakterin i-frame süresini döndürür."""
        # Ana karakterin health bileşeninde invincibility süresi varsa onu döndür
        if hasattr(self._health, 'invincible_timer'):
            return self._health.invincible_timer
        return 0.0

    @hc.setter
    def hc(self, val):
        """Level'ın yazmasına izin verilmez; sadece okunabilir. Yazma işlemi yok sayılır."""
        pass

    @property
    def dc(self):
        """Level'ın beklediği dash cooldown – ana karakterin stamina dash cooldown'unu döndürür."""
        if hasattr(self._stamina, 'dash_cooldown'):
            return self._stamina.dash_cooldown
        return 0.0

    @dc.setter
    def dc(self, val):
        """Level'ın yazmasına izin verilmez; sadece okunabilir. Yazma işlemi yok sayılır."""
        pass

    # ---- Level'ın çağıracağı metotlar ----
    def take_hit(self, cam):
        """
        Hasar alındığında çağrılır.
        PlayerEntity'nin health bileşenini kullanır ve action_queue'ya kamera sarsıntısı ekler.
        """
        # Ana karakterin hasar alma bileşenini kullan (1 birim hasar)
        self._health.take_damage(1)

        # Kamera sarsıntısı isteğini ana oyunun action queue'suna ekle
        self._main.action_queue.append({"type": "CAMERA_SHAKE", "power": 6, "duration": 0.2})

        # Geri tepme (vurulunca savrulma) – PlayerEntity'nin vx/vy'sini doğrudan değiştir
        self._main.vx = -self._facing * 160
        self._main.vy = -100

    def dash(self):
        """
        Dash mekaniği.
        Ana karakterin dash metodunu çağırır ve level'ın dash animasyonu için dt'yi ayarlar.
        """
        if self.dc <= 0:   # dc property'si ana karakterin dash cooldown'unu döndürür
            if hasattr(self._main, 'dash'):
                self._main.dash()
            elif hasattr(self._stamina, 'use_dash'):
                self._stamina.use_dash()
            self.dt = 0.13
            if self._vy > 0:
                self._vy = 0

    def update(self, dt, plats):
        """
        Fizik ve durum güncellemesi.
        Level'ın platform listesini (plats) doğrudan PlayerEntity'nin update metoduna iletir.
        PlayerEntity, kendi CCD ve platform çözümleyicisini (resolve_platforms) kullanır.
        """
        # Ana karakterin update metodu platform listesi alıyorsa
        if hasattr(self._main, 'update') and self._main.update.__code__.co_argcount > 1:
            self._main.update(dt, plats)
        else:
            # Fallback: sadece dt ile güncelle (level platformları yok sayılır, tavsiye edilmez)
            self._main.update(dt)

        # Adaptörün kendi zamanlayıcılarını güncelle (sadece level için)
        if self.dt > 0:
            self.dt = max(0.0, self.dt - dt)
        if self.ac > 0:
            self.ac = max(0.0, self.ac - dt)

        # Ana karakterin güncel değerlerini al (özellikle rect ve hız)
        self._rect = self._main.rect
        self._vx = self._main.vx
        self._vy = self._main.vy
        self._on = self._main.on_ground
        self._facing = self._main.facing
        self._alive = self._main.alive

    def draw(self, surf, ox, oy):
        """Çizim işlemini ana karaktere yönlendir."""
        self._main.draw(surf, ox, oy)

    # ---- Saldırı desteği (level'lar J tuşuna basınca) ----
    def start_attack(self):
        """
        J tuşu basıldığında level tarafından çağrılır (player.ac <= 0 ise).
        Level'ın kendi saldırı cooldown'unu ayarlar ve saldırıyı gerçekleştirmek için ana karakteri çağırmaz.
        (Level'ın kendi saldırı hitbox'ı ve hasar mekaniği çalışır.)
        """
        if self.ac <= 0:
            self.ac = 0.32   # level'ın kendi saldırı cooldown'u
            # İsteğe bağlı: ana karakterin melee sistemine hafif saldırı girdisi eklemek isterseniz
            # if hasattr(self._combos, 'add_input'):
            #     self._combos.add_input('L')
            # NOT: Bu satırı açarsanız, ana karakterin combo sistemi de tetiklenir ve
            # kendi vuruş efektlerini (partikül, ses) oynatır. Ancak level'ın hasar vermesi
            # ayrıca gerçekleşir. İkisi aynı anda olabilir veya biri kapatılabilir.
            # Varsayılan olarak sadece level'ın saldırısı kullanılır.

    def get_attack_rect(self):
        """
        Level'ın saldırı hitbox'ını oluşturması için gerekli.
        Ana karakterin melee sisteminden hitbox alır, yoksa varsayılan bir değer döndürür.
        """
        if hasattr(self._combos, 'get_hitbox'):
            return self._combos.get_hitbox()
        # Varsayılan: karakterin önündeki bir alan (level1-4'te kullanılan yaklaşık menzil)
        cx = self.rect.centerx + self.f * 52
        return pygame.Rect(cx - 18, self.rect.y, 36, self.H)