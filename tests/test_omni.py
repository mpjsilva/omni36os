"""Testes do Omni36OS que rodam no PC (sem o console). Rodar: python3 tests/run.py

Cobrem o que já quebrou ou pode deixar o console sem uso: gravação de configuração, atalhos,
botão de power, bateria crítica, atualização com volta, backup e a interface inteira (simulador
sem janela).
"""
import io
import json
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = os.path.join(ROOT, "port", "omni36os")
sys.path.insert(0, PORT)

# no PC não existe o usuário ark do console
_real_getpwnam = pwd.getpwnam
pwd.getpwnam = lambda n: _real_getpwnam(os.environ.get("USER") or "root") if n == "ark" else _real_getpwnam(n)

import omni  # noqa: E402
import omni_combos as oc  # noqa: E402


class SaveFile(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_grava_inteiro_e_sem_sobra(self):
        p = os.path.join(self.d, "sub", "conf.json")
        omni.save_file(p, '{"a": 1}')
        omni.save_file(p, '{"a": 2}')
        self.assertEqual(open(p).read(), '{"a": 2}')
        self.assertEqual(os.listdir(os.path.dirname(p)), ["conf.json"])

    def test_mantem_permissoes(self):
        p = os.path.join(self.d, "x")
        omni.save_file(p, "1")
        os.chmod(p, 0o640)
        omni.save_file(p, "2")
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o640)

    def test_erro_nao_estraga_o_antigo(self):
        p = os.path.join(self.d, "x")
        omni.save_file(p, "bom")

        class Ruim:
            def __str__(self):
                raise RuntimeError("falhou no meio")
        with self.assertRaises(RuntimeError):
            omni.save_file(p, Ruim())
        self.assertEqual(open(p).read(), "bom")
        self.assertEqual(os.listdir(self.d), ["x"])


class Atalhos(unittest.TestCase):
    def test_config_estragada_vira_padrao(self):
        self.assertEqual(oc.normalize("lixo"), oc.defaults())
        self.assertEqual(oc.normalize({"combos": {"fps": [999, 1]}})["combos"]["fps"], oc.ACTIONS["fps"][3])

    def test_fechar_e_fixo(self):
        c = oc.normalize({"combos": {"fechar": [oc.FN, 305]}})
        self.assertEqual(c["combos"]["fechar"], [oc.SELECT, oc.START])
        self.assertIsNotNone(oc.problem("fechar", [oc.FN, 305], c["combos"]))

    def test_conflitos(self):
        d = oc.defaults()["combos"]
        self.assertIsNotNone(oc.problem("fps", [oc.FN, 544], d))         # brilho do sistema
        self.assertIsNotNone(oc.problem("fps", [oc.FN, 304], d))         # já é do limite
        self.assertIsNotNone(oc.problem("fps", [oc.FN, 116], d))         # power
        self.assertIsNone(oc.problem("fps", [oc.FN, 313], d))


class Wifi(unittest.TestCase):
    def test_campos_do_nmcli(self):
        import omni_sistema
        self.assertEqual(omni_sistema._nm_fields(r"*:Minha\:Rede:80:WPA2"), ["*", "Minha:Rede", "80", "WPA2"])
        self.assertEqual(omni_sistema._nm_fields(r"::0:"), ["", "", "0", ""])


class Backup(unittest.TestCase):
    def test_importacao_nao_sai_do_modulo(self):
        import omni_backup as b
        home = b.HOME.lstrip("/")
        self.assertTrue(b.allowed("omni36os", f"{home}/.config/omni36os/tema"))
        self.assertFalse(b.allowed("omni36os", f"{home}/.bashrc"))
        self.assertFalse(b.allowed("omni36os", f"{home}/.config/omni36os/../../.bashrc"))
        self.assertFalse(b.allowed("omni36os", "etc/shadow"))


class Power(unittest.TestCase):
    def setUp(self):
        import power_button as pb
        self.pb = pb
        self.d = tempfile.mkdtemp()
        self.saved = {k: getattr(pb, k) for k in ("SHM", "PRESS", "PENDING", "MENU_FLAG", "UI_PID", "safe",
                                                     "ui_pids", "front")}
        pb.SHM = self.d
        pb.PRESS, pb.PENDING, pb.MENU_FLAG, pb.UI_PID = (os.path.join(self.d, n) for n in ("press", "pending", "menu", "ui"))
        self.off = []
        pb.safe = self.off.append
        pb.front = lambda: []
        self.signals = []
        self.real_kill = os.kill
        os.kill = lambda pid, sig: self.signals.append((pid, sig))

    def tearDown(self):
        os.kill = self.real_kill
        for k, v in self.saved.items():
            setattr(self.pb, k, v)
        shutil.rmtree(self.d)

    def test_toque_abre_o_menu(self):
        self.pb.ui_pids = lambda: [4242]
        self.assertEqual(self.pb.menu(), 0)
        self.assertEqual(self.signals[0][0], 4242)
        self.assertEqual(self.off, [])

    def test_aviso_velho_nao_suspende(self):
        """Regressão 1.7.0: um 'menu na tela' de outro processo fazia todo toque suspender."""
        self.pb.ui_pids = lambda: [4242]
        open(self.pb.PRESS, "w").write("1111")
        self.assertEqual(self.pb.menu(), 0)
        self.assertEqual(self.off, [])
        self.assertTrue(self.signals)

    def test_segundo_toque_com_menu_desliga(self):
        self.pb.ui_pids = lambda: [4242]
        open(self.pb.PRESS, "w").write("4242")
        self.assertEqual(self.pb.menu(), 0)
        self.assertEqual(self.off, ["poweroff"])

    def test_sem_omni36os_cai_no_original(self):
        self.pb.ui_pids = lambda: []
        self.assertEqual(self.pb.menu(), 1)


class Bateria(unittest.TestCase):
    def setUp(self):
        import omni_atalho as at
        self.at = at
        self.saved = (at.battery, at.notify, at.safe_poweroff, at.BAT_EVERY, at.time.sleep)
        self.msgs, self.offs = [], []
        at.notify, at.safe_poweroff, at.BAT_EVERY = (lambda t, m: self.msgs.append(m)), lambda: self.offs.append(1), 0
        at.time.sleep = lambda s: None

    def tearDown(self):
        at = self.at
        at.battery, at.notify, at.safe_poweroff, at.BAT_EVERY, at.time.sleep = self.saved

    def run_guard(self, readings):
        it = iter(readings)
        self.at.battery = lambda: next(it)
        g = self.at.BatteryGuard()
        for _ in readings:
            g.last = 0
            g.tick()

    def test_desliga_em_10_so_com_duas_leituras(self):
        self.run_guard([(10, 3600, False), (40, 3900, False), (10, 3600, False)])
        self.assertEqual(self.offs, [])
        self.run_guard([(11, 3600, False), (11, 3600, False)])
        self.assertEqual(self.offs, [])
        self.run_guard([(10, 3600, False), (10, 3600, False), (9, 3550, False)])
        self.assertEqual(self.offs, [1])                 # uma vez só

    def test_tensao_baixa_tambem_desliga(self):
        self.run_guard([(9, 3300, False), (9, 3300, False)])
        self.assertEqual(self.offs, [1])

    def test_carregando_nunca_desliga(self):
        self.run_guard([(1, 3300, True)] * 4)
        self.assertEqual(self.offs, [])

    def test_avisos_30_e_15_uma_vez_cada(self):
        self.run_guard([(31, 3800, False), (30, 3790, False), (25, 3750, False), (15, 3700, False),
                        (14, 3690, False), (12, 3680, False)])
        self.assertEqual(len(self.msgs), 2)
        self.assertIn("carregador", self.msgs[0])
        self.assertIn("Salve seu progresso", self.msgs[1])
        self.assertEqual(self.offs, [])

    def test_caiu_direto_para_15_so_pede_para_fechar(self):
        self.run_guard([(15, 3700, False), (14, 3690, False)])
        self.assertEqual(len(self.msgs), 1)
        self.assertIn("Salve seu progresso", self.msgs[0])

    def test_carregou_e_descarregou_avisa_de_novo(self):
        self.run_guard([(30, 3800, False), (30, 3800, True), (29, 3790, False)])
        self.assertEqual(len(self.msgs), 2)


class SomAutomatico(unittest.TestCase):
    def setUp(self):
        import omni_audio as a
        self.a = a
        self.saved = (a.jack_device, a.headphones_in, a.current_path, a.amixer, a.time.monotonic)
        self.path, self.sets, self.clock = ["SPK"], [], [100.0]
        a.jack_device = lambda: "/dev/input/event9"
        a.current_path = lambda: self.path[0]

        def mixer(*args):
            if args[:2] == ("-q", "cset"):
                self.path[0] = args[-1]
                self.sets.append(args[-1])
            return ""
        a.amixer = mixer
        a.time.monotonic = lambda: self.clock[0]

    def tearDown(self):
        a = self.a
        a.jack_device, a.headphones_in, a.current_path, a.amixer, a.time.monotonic = self.saved

    def step(self, hp, secs=1.1):
        self.a.headphones_in = lambda dev=None: hp
        self.clock[0] += secs
        self.r.tick()

    def test_troca_com_o_fone(self):
        self.r = self.a.AutoRoute()
        self.step(True)                       # fone já encaixado no boot
        self.assertEqual(self.path[0], "HP")
        self.step(True)
        self.step(False)                      # tirou o fone
        self.assertEqual(self.path[0], "SPK")
        self.assertEqual(self.sets, ["HP", "SPK"])

    def test_corrige_se_alguem_mudar(self):
        self.r = self.a.AutoRoute()
        self.step(False)
        self.path[0] = "SPK_HP"               # um jogo mexeu na saída
        self.step(False, secs=11)
        self.assertEqual(self.path[0], "SPK")

    def test_sem_deteccao_nao_mexe(self):
        self.a.jack_device = lambda: None
        self.r = self.a.AutoRoute()
        self.step(None)
        self.assertEqual(self.sets, [])


class Atualizacao(unittest.TestCase):
    def setUp(self):
        import omni_update as u
        self.u = u
        self.d = tempfile.mkdtemp()
        self.saved = {k: getattr(u, k) for k in ("OMNI", "NEW", "PREV", "STATE", "PENDING", "TRIES", "ROLLED", "_get")}
        u.OMNI = os.path.join(self.d, "opt", "omni36os")
        u.NEW, u.PREV = u.OMNI + ".new", u.OMNI + ".prev"
        u.STATE = os.path.join(self.d, "state")
        u.PENDING, u.TRIES, u.ROLLED = (os.path.join(u.STATE, n) for n in ("pending", "tries", "rolled-back"))
        shutil.copytree(PORT, u.OMNI, ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(u.OMNI, "logs"))
        open(os.path.join(u.OMNI, "logs", "x"), "w").write("deste console")
        open(os.path.join(u.OMNI, "VERSION"), "w").write("1.0.0\n")
        self.real_run = subprocess.run
        u.subprocess.run = lambda cmd, **k: None if cmd[0] == "systemd-run" else self.real_run(cmd, **k)

    def tearDown(self):
        self.u.subprocess.run = self.real_run
        for k, v in self.saved.items():
            setattr(self.u, k, v)
        shutil.rmtree(self.d)

    def pack(self, version, broken=False, escape=False):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            t.add(PORT, arcname=f"omni36os-omni-v{version}/port/omni36os",
                  filter=lambda i: None if "__pycache__" in i.name else i)
            for name, data in (("VERSION", version + "\n"), ("quebrado.py", "def x(:\n" if broken else "x = 1\n")):
                ti = tarfile.TarInfo(f"omni36os-omni-v{version}/port/omni36os/{name}")
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data.encode()))
            if escape:                           # tentativa de gravar fora da pasta
                ti = tarfile.TarInfo(f"omni36os-omni-v{version}/port/omni36os/../../../fora.txt")
                ti.size = 1
                t.addfile(ti, io.BytesIO(b"x"))
        return buf.getvalue()

    def test_versao_quebrada_nao_instala(self):
        self.u._get = lambda url, timeout=0: self.pack("2.0.0", broken=True)
        msg = self.u.install("omni-v2.0.0", "2.0.0")
        self.assertTrue(msg.startswith("Não instalei"))
        self.assertEqual(self.u.current(), "1.0.0")
        self.assertFalse(os.path.exists(self.u.NEW))

    def test_instala_guarda_a_anterior_e_volta(self):
        self.u._get = lambda url, timeout=0: self.pack("2.0.0")
        self.u.install("omni-v2.0.0", "2.0.0")
        self.assertEqual(self.u.current(), "2.0.0")
        self.assertEqual(open(os.path.join(self.u.PREV, "VERSION")).read().strip(), "1.0.0")
        self.assertEqual(open(os.path.join(self.u.OMNI, "logs", "x")).read(), "deste console")
        self.assertTrue(os.path.exists(self.u.PENDING))
        self.u.go_back()
        self.assertEqual(self.u.current(), "1.0.0")
        self.assertFalse(os.path.exists(self.u.PENDING))

    def test_guarda_volta_depois_de_3_tentativas(self):
        self.u._get = lambda url, timeout=0: self.pack("2.0.0")
        self.u.install("omni-v2.0.0", "2.0.0")
        guard = open(os.path.join(PORT, "omni36os-start")).read()
        guard = (guard.replace("D=/opt/omni36os", f"D={self.u.OMNI}").replace("P=/opt/omni36os.prev", f"P={self.u.PREV}")
                 .replace("S=/var/lib/omni36os-update", f"S={self.u.STATE}").replace("sudo ", "")
                 .replace('exec "$D/launch-direct.sh"', 'cat "$D/VERSION"').replace("systemctl restart", "true"))
        g = os.path.join(self.d, "guard.sh")
        open(g, "w").write(guard)
        seen = [subprocess.run(["bash", g], capture_output=True, text=True).stdout.strip() for _ in range(4)]
        self.assertEqual(seen, ["2.0.0", "2.0.0", "2.0.0", "1.0.0"])
        self.assertIn("2.0.0", self.u.rolled_back_message())

    def test_pacote_que_tenta_sair_e_recusado(self):
        self.u._get = lambda url, timeout=0: self.pack("2.0.0", escape=True)
        self.assertTrue(self.u.install("omni-v2.0.0", "2.0.0").startswith("Não instalei"))
        self.assertEqual(self.u.current(), "1.0.0")
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.d), "fora.txt")))

    def test_menu_aberto_aprova(self):
        self.u._get = lambda url, timeout=0: self.pack("2.0.0")
        self.u.install("omni-v2.0.0", "2.0.0")
        self.u.confirm_ok()
        self.assertFalse(os.path.exists(self.u.PENDING))


class Scripts(unittest.TestCase):
    def test_sintaxe_dos_sh(self):
        for n in sorted(os.listdir(PORT)):
            if n.endswith(".sh") or n == "omni36os-start":
                r = subprocess.run(["bash", "-n", os.path.join(PORT, n)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{n}: {r.stderr}")

    def test_python_sem_erros(self):
        try:
            import pyflakes  # noqa: F401
        except ImportError:
            self.skipTest("pyflakes não instalado")
        r = subprocess.run([sys.executable, "-m", "pyflakes", *[os.path.join(PORT, n) for n in sorted(os.listdir(PORT))
                                                               if n.endswith(".py")]], capture_output=True, text=True)
        erros = [ln for ln in r.stdout.splitlines()
                 if "imported but unused" not in ln and "assigned to but never used" not in ln]
        self.assertEqual(erros, [])

    def test_novidades_e_versao(self):
        import omni_help
        v = open(os.path.join(PORT, "VERSION")).read().strip()
        self.assertEqual(omni_help.NOVIDADES[0][0], v, "VERSION e NOVIDADES (omni_help.py) diferentes")
        self.assertIn(f"## {v} ", open(os.path.join(ROOT, "NOVIDADES.md")).read(), "falta a versão no NOVIDADES.md")


class Interface(unittest.TestCase):
    """O simulador sem janela: abre cada card, desce por todos os itens e volta, sem nenhum erro."""

    def test_percorre_todos_os_cards(self):
        steps = ["wait2500"]
        for i in range(9):
            r, c = divmod(i, 3)
            nav = ["down"] * r + ["right"] * c
            back = [{"down": "up", "right": "left"}[n] for n in nav]
            steps += nav + ["ok", "wait300"] + ["down"] * 12 + ["back", "wait300"] + back
        env = dict(os.environ, SDL_VIDEODRIVER="offscreen", OMNI_FAKE="1", OMNI_JOGADOR="Teste", OMNI_DEMO_STEP="0.12",
                   OMNI_DEMO=",".join(steps + ["quit"]))
        r = subprocess.run([sys.executable, "omni_ui.py"], cwd=PORT, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertNotIn("Traceback", r.stderr, r.stderr[-2000:])



class TelaCerta(unittest.TestCase):
    """omni_painel: lista de telas, troca de DTB e volta dos originais, numa /boot de mentira."""
    CAT = os.path.expanduser("~/Apps/Omni36OS/cartao/BOOT/dtb")

    def setUp(self):
        if not os.path.isdir(self.CAT) or not shutil.which("fdtget"):
            self.skipTest("sem catálogo de DTBs ou fdtget")
        import omni_painel as op
        self.op, self.tmp = op, tempfile.mkdtemp()
        boot = self.tmp
        for v, name in (("r36s", "R36S-V21 2024-12-18 2529"), ("r36s", "R36S-V21 2024-12-18 2544"),
                        ("r36s", "R36S-V12 2023-08-18 Panel 0"), ("clone", "G80C-MB V1.1-20250319 Panel 9"),
                        ("r36s", "HL-R45H-V20 2025-11-18")):
            shutil.copytree(f"{self.CAT}/{v}/{name}", f"{boot}/dtb/{v}/{name}")
        shutil.copy(f"{self.CAT}/r36s/R36S-V21 2024-12-18 2529/rk3326-r36s-linux.dtb", boot)
        with open(f"{boot}/boot.ini", "w") as f:
            f.write("original\n")
        self.saved = {k: getattr(op, k) for k in ("BOOT", "CATALOG", "DIR", "STATE", "ORIG", "DONE", "RETRY", "LOG")}
        op.BOOT, op.CATALOG, op.DIR = boot, f"{boot}/dtb", f"{boot}/omni36os-tela"
        op.STATE, op.ORIG, op.DONE = f"{op.DIR}/estado.json", f"{op.DIR}/original", f"{op.DIR}/pronto"
        op.RETRY, op.LOG = f"{op.DIR}/testar", f"{op.DIR}/log.txt"
        info = op.panel_info(f"{boot}/rk3326-r36s-linux.dtb")
        self.live = info[0]
        self.saved_live = op.panel_hash_live
        op.panel_hash_live = lambda: self.live

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(self.op, k, v)
        self.op.panel_hash_live = self.saved_live
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lista(self):
        lst = self.op.candidates("r36s")
        self.assertTrue(lst[0]["atual"])                       # a tela de agora vem primeiro (sem reiniciar)
        self.assertEqual(lst[0]["iguais"], 2)                  # 2529 e 2544 são a mesma tela: testa uma vez
        self.assertTrue(os.path.basename(lst[0]["pasta"]).startswith("R36S-"))
        self.assertFalse(any("R45H" in c["pasta"] for c in lst))   # 720x720: não é tela de R36S
        self.assertIn("clone", lst[-1]["pasta"])               # a outra família por último
        self.assertIn("clone", self.op.candidates("clone")[1]["pasta"])

    def test_troca_e_volta(self):
        op = self.op
        orig = open(f"{op.BOOT}/rk3326-r36s-linux.dtb", "rb").read()
        op.save_original()
        op.install(f"{op.CATALOG}/clone/G80C-MB V1.1-20250319 Panel 9")
        self.assertNotEqual(open(f"{op.BOOT}/rk3326-r36s-linux.dtb", "rb").read(), orig)
        self.assertNotEqual(open(f"{op.BOOT}/boot.ini").read(), "original\n")
        op.restore_original()
        self.assertEqual(open(f"{op.BOOT}/rk3326-r36s-linux.dtb", "rb").read(), orig)
        self.assertEqual(open(f"{op.BOOT}/boot.ini").read(), "original\n")

    def test_so_no_primeiro_boot(self):
        self.assertFalse(self.op.needed())                     # cartão já usado: não faz nada
        open(f"{self.op.BOOT}/firstboot.sh", "w").close()
        self.assertTrue(self.op.needed())


if __name__ == "__main__":
    unittest.main()
