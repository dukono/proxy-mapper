"""Certificate Settings Dialog — mitmproxy certificate management."""

import os
import shutil
import subprocess
from pathlib import Path

from nicegui import ui
from utils import get_logger

log = get_logger("CERT_SETTINGS")

MITMPROXY_CERT_DIR = Path.home() / ".mitmproxy"
MITMPROXY_CA_CERT = MITMPROXY_CERT_DIR / "mitmproxy-ca-cert.pem"
MITMPROXY_CA_CERT_P12 = MITMPROXY_CERT_DIR / "mitmproxy-ca-cert.p12"
MITMPROXY_CA_CERT_CER = MITMPROXY_CERT_DIR / "mitmproxy-ca-cert.cer"

DEFAULT_JAVA_CACERTS = str(Path.home() / ".asdf/installs/ivm-java/openjdk-21.0.10/lib/security/cacerts")
DEFAULT_JAVA_CACERTS_PASSWORD = "changeit"
CERT_ALIAS = "mitmproxy"


class CertSettingsDialog:
    """Dialog for mitmproxy certificate management."""

    def __init__(self):
        self.dialog = None
        self._java_cacerts_input = None
        self._output_label = None
        self._cert_status_icon = None
        self._cert_status_label = None
        self._cert_buttons_row = None

    def _refresh_cert_status(self):
        """Refresh the certificate status section dynamically."""
        cert_exists = MITMPROXY_CA_CERT.exists()
        status_color = 'text-green-400' if cert_exists else 'text-yellow-400'
        status_icon = 'check_circle' if cert_exists else 'warning'
        status_text = f'Found: {MITMPROXY_CA_CERT}' if cert_exists else 'Not found — start the proxy once to generate it'

        self._cert_status_icon.props(f'name={status_icon}')
        self._cert_status_icon.classes(status_color, remove='text-green-400 text-yellow-400')
        self._cert_status_label.set_text(status_text)
        self._cert_status_label.classes(status_color, remove='text-green-400 text-yellow-400 text-xs')
        self._cert_status_label.classes('text-xs')

        self._cert_buttons_row.set_visibility(cert_exists)

    def show(self):
        self._output_lines = []

        with ui.dialog() as self.dialog:
            self.dialog.props('persistent')
            # Override Quasar's inner dialog container so it doesn't fight resize
            ui.add_css('''
                .cert-dialog > .q-dialog__inner {
                    max-width: none !important;
                    max-height: none !important;
                    padding: 0 !important;
                    pointer-events: none;
                }
                .cert-dialog-card {
                    pointer-events: all;
                    position: fixed !important;
                    top: 50% !important;
                    left: 50% !important;
                    transform: translate(-50%, -50%) !important;
                    display: flex !important;
                    flex-direction: column !important;
                    resize: both;
                    overflow: hidden !important;
                    width: 680px;
                    min-width: 420px;
                    height: 600px;
                    min-height: 300px;
                }
                .cert-dialog-card .cert-scroll {
                    flex: 1 !important;
                    min-height: 0 !important;
                    overflow-y: auto !important;
                }
            ''')
            self.dialog.classes('cert-dialog')

            with ui.card().classes('bg-gray-800 p-0 cert-dialog-card'):
                # Header — fixed height, no shrink
                with ui.row().classes('w-full px-4 py-3 border-b border-gray-700 items-center justify-between shrink-0'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('security').classes('text-blue-400 text-xl')
                        ui.label('Certificate Settings').classes('text-base font-bold text-white')
                    ui.button(icon='close', on_click=self.dialog.close).props('flat round dense color=white')

                # Scrollable body — grows to fill remaining space
                with ui.element('div').classes('cert-scroll w-full p-4'):
                    with ui.column().classes('w-full gap-4'):

                        # ── Section: mitmproxy certificate status ─────────────
                        with ui.card().classes('w-full bg-gray-700/50 border border-gray-600 p-3'):
                            with ui.row().classes('items-center justify-between mb-2'):
                                ui.label('mitmproxy CA Certificate').classes('text-sm font-bold text-blue-300')
                                ui.button(icon='refresh', on_click=self._refresh_cert_status) \
                                    .props('flat round dense color=gray').tooltip('Refresh status')

                            with ui.row().classes('items-center gap-2 mb-3'):
                                self._cert_status_icon = ui.icon('warning').classes('text-yellow-400 text-sm')
                                self._cert_status_label = ui.label('Checking...').classes('text-yellow-400 text-xs')

                            with ui.row().classes('gap-2 flex-wrap') as self._cert_buttons_row:
                                ui.button('📋 Copy cert path', on_click=lambda: self._copy_to_clipboard(str(MITMPROXY_CA_CERT))) \
                                    .props('flat dense no-caps size=sm').classes('text-gray-300 hover:text-white')
                                ui.button('📁 Open folder', on_click=lambda: self._open_folder(str(MITMPROXY_CERT_DIR))) \
                                    .props('flat dense no-caps size=sm').classes('text-gray-300 hover:text-white')

                        # ── Section: Export certificate ───────────────────────
                        with ui.card().classes('w-full bg-gray-700/50 border border-gray-600 p-3'):
                            ui.label('Export Certificate').classes('text-sm font-bold text-blue-300 mb-2')
                            ui.label('Export the mitmproxy CA cert in different formats for installation in browsers, OS or Java.') \
                                .classes('text-xs text-gray-400 mb-3')

                            with ui.row().classes('gap-2 flex-wrap'):
                                ui.button('Export .pem', icon='download', on_click=lambda: self._export_cert('pem')) \
                                    .props('flat dense no-caps size=sm').classes('text-blue-300 hover:text-white border border-gray-600')
                                ui.button('Export .cer', icon='download', on_click=lambda: self._export_cert('cer')) \
                                    .props('flat dense no-caps size=sm').classes('text-blue-300 hover:text-white border border-gray-600')
                                ui.button('Export .p12', icon='download', on_click=lambda: self._export_cert('p12')) \
                                    .props('flat dense no-caps size=sm').classes('text-blue-300 hover:text-white border border-gray-600')

                        # ── Section: Install in Java cacerts ──────────────────
                        with ui.card().classes('w-full bg-gray-700/50 border border-gray-600 p-3'):
                            ui.label('Install in Java Keystore (cacerts)').classes('text-sm font-bold text-green-300 mb-2')
                            ui.label('Installs the mitmproxy CA cert into a Java cacerts keystore using keytool.') \
                                .classes('text-xs text-gray-400 mb-3')

                            ui.label('cacerts path:').classes('text-xs text-gray-400')
                            self._java_cacerts_input = ui.input(
                                value=self._find_cacerts()
                            ).classes('w-full').props('dark outlined dense input-class=text-xs')

                            with ui.row().classes('gap-2 mt-3'):
                                ui.button('Install cert in Java', icon='verified_user',
                                          on_click=self._install_in_java) \
                                    .props('dense no-caps').classes(
                                    'bg-green-700 text-white hover:bg-green-600 px-3')
                                ui.button('Check if installed', icon='search',
                                          on_click=self._check_java_cert) \
                                    .props('flat dense no-caps').classes('text-gray-300 hover:text-white border border-gray-600')
                                ui.button('Remove from Java', icon='delete',
                                          on_click=self._remove_from_java) \
                                    .props('flat dense no-caps').classes('text-red-400 hover:text-red-300 border border-gray-600')

                        # ── Output console ────────────────────────────────────
                        with ui.card().classes('w-full bg-gray-900 border border-gray-700 p-3'):
                            ui.label('Output').classes('text-xs font-bold text-gray-400 mb-2')
                            self._output_label = ui.label('Ready.') \
                                .classes('text-xs text-gray-300 whitespace-pre-wrap font-mono')

        self.dialog.open()
        # Refresh status after dialog is built
        self._refresh_cert_status()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_cacerts(self) -> str:
        candidates = [DEFAULT_JAVA_CACERTS]

        # Try all asdf ivm-java installs (note: ivm-java, not jvm-java)
        for asdf_dir in ['ivm-java', 'jvm-java']:
            asdf_jvm = Path.home() / f".asdf/installs/{asdf_dir}"
            if asdf_jvm.exists():
                for jdk in sorted(asdf_jvm.iterdir()):
                    c = jdk / "lib/security/cacerts"
                    if c.exists():
                        candidates.insert(0, str(c))

        for c in candidates:
            if os.path.exists(c):
                return c
        return DEFAULT_JAVA_CACERTS

    def _set_output(self, text: str, color: str = 'text-gray-300'):
        self._output_label.set_text(text)
        self._output_label.classes(f'text-xs whitespace-pre-wrap font-mono {color}', remove='text-gray-300 text-green-400 text-red-400 text-yellow-400')

    def _copy_to_clipboard(self, text: str):
        ui.run_javascript(f'navigator.clipboard.writeText({repr(text)})')
        ui.notify(f'Copied: {text}', type='positive')

    def _open_folder(self, path: str):
        try:
            subprocess.Popen(['xdg-open', path])
        except Exception as e:
            ui.notify(f'Error opening folder: {e}', type='negative')

    def _export_cert(self, fmt: str):
        if not MITMPROXY_CA_CERT.exists():
            self._set_output('❌ mitmproxy cert not found. Start the proxy first.', 'text-red-400')
            return

        try:
            dest_dir = Path.home() / "Desktop"
            if not dest_dir.exists():
                dest_dir = Path.home()

            if fmt == 'pem':
                dest = dest_dir / "mitmproxy-ca-cert.pem"
                shutil.copy2(MITMPROXY_CA_CERT, dest)
                self._set_output(f'✅ Exported PEM to:\n{dest}', 'text-green-400')

            elif fmt == 'cer':
                dest = dest_dir / "mitmproxy-ca-cert.cer"
                if MITMPROXY_CA_CERT_CER.exists():
                    shutil.copy2(MITMPROXY_CA_CERT_CER, dest)
                else:
                    # Convert PEM → DER (cer)
                    result = subprocess.run(
                        ['openssl', 'x509', '-in', str(MITMPROXY_CA_CERT),
                         '-outform', 'DER', '-out', str(dest)],
                        capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        self._set_output(f'❌ openssl error:\n{result.stderr}', 'text-red-400')
                        return
                self._set_output(f'✅ Exported CER to:\n{dest}', 'text-green-400')

            elif fmt == 'p12':
                dest = dest_dir / "mitmproxy-ca-cert.p12"
                if MITMPROXY_CA_CERT_P12.exists():
                    shutil.copy2(MITMPROXY_CA_CERT_P12, dest)
                    self._set_output(f'✅ Exported P12 to:\n{dest}', 'text-green-400')
                else:
                    self._set_output('❌ .p12 file not found in ~/.mitmproxy', 'text-red-400')

            ui.notify(f'Exported {fmt.upper()} to {dest}', type='positive')

        except Exception as e:
            self._set_output(f'❌ Export error: {e}', 'text-red-400')
            log.error("Export cert error: %s", e)

    def _run_keytool(self, args: list) -> tuple[int, str, str]:
        """Run keytool and return (returncode, stdout, stderr)."""
        # Find keytool alongside the cacerts file
        cacerts_path = self._java_cacerts_input.value.strip()
        keytool = 'keytool'

        # Try to find keytool in the same JDK
        jdk_bin = Path(cacerts_path).parent.parent.parent / 'bin' / 'keytool'
        if jdk_bin.exists():
            keytool = str(jdk_bin)

        cmd = [keytool] + args
        log.info("Running: %s", ' '.join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def _install_in_java(self):
        if not MITMPROXY_CA_CERT.exists():
            self._set_output('❌ mitmproxy cert not found. Start the proxy first.', 'text-red-400')
            return

        cacerts_path = self._java_cacerts_input.value.strip()
        if not os.path.exists(cacerts_path):
            self._set_output(f'❌ cacerts not found at:\n{cacerts_path}', 'text-red-400')
            return

        self._set_output('⏳ Installing certificate...', 'text-yellow-400')

        # First remove old alias if it exists (ignore error)
        self._run_keytool([
            '-delete', '-alias', CERT_ALIAS,
            '-keystore', cacerts_path,
            '-storepass', DEFAULT_JAVA_CACERTS_PASSWORD,
            '-noprompt'
        ])

        rc, out, err = self._run_keytool([
            '-importcert',
            '-alias', CERT_ALIAS,
            '-file', str(MITMPROXY_CA_CERT),
            '-keystore', cacerts_path,
            '-storepass', DEFAULT_JAVA_CACERTS_PASSWORD,
            '-noprompt',
            '-trustcacerts',
        ])

        if rc == 0:
            self._set_output(f'✅ Certificate installed successfully!\nAlias: {CERT_ALIAS}\nKeystore: {cacerts_path}', 'text-green-400')
            ui.notify('Certificate installed in Java keystore', type='positive')
        else:
            output = (out + err).strip()
            self._set_output(f'❌ keytool error (exit {rc}):\n{output}', 'text-red-400')
            ui.notify('Failed to install certificate', type='negative')
        log.info("keytool install rc=%d out=%s err=%s", rc, out, err)

    def _check_java_cert(self):
        cacerts_path = self._java_cacerts_input.value.strip()
        if not os.path.exists(cacerts_path):
            self._set_output(f'❌ cacerts not found at:\n{cacerts_path}', 'text-red-400')
            return

        rc, out, err = self._run_keytool([
            '-list',
            '-alias', CERT_ALIAS,
            '-keystore', cacerts_path,
            '-storepass', DEFAULT_JAVA_CACERTS_PASSWORD,
        ])

        if rc == 0:
            self._set_output(f'✅ Certificate IS installed:\n{out.strip()}', 'text-green-400')
        else:
            self._set_output(f'⚠️ Certificate NOT found (alias: {CERT_ALIAS})\n{err.strip()}', 'text-yellow-400')

    def _remove_from_java(self):
        cacerts_path = self._java_cacerts_input.value.strip()
        if not os.path.exists(cacerts_path):
            self._set_output(f'❌ cacerts not found at:\n{cacerts_path}', 'text-red-400')
            return

        rc, out, err = self._run_keytool([
            '-delete',
            '-alias', CERT_ALIAS,
            '-keystore', cacerts_path,
            '-storepass', DEFAULT_JAVA_CACERTS_PASSWORD,
            '-noprompt',
        ])

        if rc == 0:
            self._set_output(f'✅ Certificate removed from keystore.\nAlias: {CERT_ALIAS}', 'text-green-400')
            ui.notify('Certificate removed from Java keystore', type='positive')
        else:
            output = (out + err).strip()
            self._set_output(f'❌ keytool error (exit {rc}):\n{output}', 'text-red-400')
            ui.notify('Failed to remove certificate', type='negative')
