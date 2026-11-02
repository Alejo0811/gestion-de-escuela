/* Optional integration test. Uses an isolated SQLite database, never club data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'tennis-sync-'));
  const root = path.resolve(__dirname, '..');
  const server = spawn(process.env.PYTHON_BIN || 'python3', ['server.py', '--port', '0'], {
    cwd: root, env: {...process.env, TENNIS_DB: path.join(temporary, 'test.sqlite3')},
    stdio: ['ignore', 'pipe', 'pipe']
  });
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('El servidor no ha arrancado')), 10000);
      server.once('error', reject);
      server.once('exit', code => {clearTimeout(timer);reject(Error(`Servidor cerrado: ${code}`))});
      server.stderr.on('data', chunk => process.stderr.write(chunk));
      server.stdout.on('data', chunk => {
        const match = String(chunk).match(/puerto (\d+)/);
        if (match) {clearTimeout(timer);resolve(match[1])}
      });
    });
    const executablePath = process.env.CHROMIUM_PATH || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
    browser = await chromium.launch({executablePath, headless: true, args: ['--no-sandbox']});
    const pcContext = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const mobileContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    const pc = await pcContext.newPage(), mobile = await mobileContext.newPage();
    const errors = [];
    for (const page of [pc, mobile]) {
      page.on('pageerror', error => errors.push(error.message));
      page.setDefaultTimeout(15000);
      await page.goto(`http://127.0.0.1:${port}`);
      await page.getByRole('button', {name: 'Explorar como gestor'}).click();
      await page.getByRole('heading', {name: 'Un grupo para cada jugador'}).waitFor();
      await page.locator('[data-page="catalog"]').click();
    }
    async function editLevel(page, oldName, newName) {
      const row = page.locator('.list-row').filter({has: page.getByText(oldName, {exact: true})});
      await row.getByRole('button', {name: 'Editar', exact: true}).click();
      await page.locator('dialog input[name="name"]').fill(newName);
      await page.locator('dialog').getByRole('button', {name: 'Guardar', exact: true}).click();
      await page.waitForFunction(() => !document.querySelector('dialog').open);
    }
    await editLevel(pc, 'Iniciación', 'Desde el ordenador');
    await mobile.getByText('Desde el ordenador', {exact: true}).waitFor();
    console.log('PASS: PC → móvil sin recargar');

    await editLevel(mobile, 'Desde el ordenador', 'Desde el móvil');
    await pc.getByText('Desde el móvil', {exact: true}).waitFor();
    console.log('PASS: móvil → PC sin recargar');

    await pc.locator('[data-action="catalog-form"][data-kind="coach"]').first().click();
    await pc.locator('dialog input[name="name"]').fill('Borrador que se conserva');
    await editLevel(mobile, 'Desde el móvil', 'Cambio mientras edito');
    await pc.locator('#sync-status[data-state="pending"]').waitFor();
    assert.equal(await pc.locator('dialog input[name="name"]').inputValue(), 'Borrador que se conserva');
    await pc.locator('dialog [data-action="dismiss"]').first().click();
    await pc.getByText('Cambio mientras edito', {exact: true}).waitFor();
    console.log('PASS: los cambios remotos conservan un formulario abierto');

    await pcContext.setOffline(true);
    await pc.locator('#sync-status[data-state="offline"]').waitFor();
    await editLevel(mobile, 'Cambio mientras edito', 'Cambio con PC sin conexión');
    await pcContext.setOffline(false);
    await pc.getByText('Cambio con PC sin conexión', {exact: true}).waitFor();
    console.log('PASS: aviso sin conexión y actualización al reconectar');

    // A delayed poll containing old data cannot replace a later local save.
    let captured, release;
    const responseCaptured = new Promise(resolve => {captured = resolve});
    const responseGate = new Promise(resolve => {release = resolve});
    let hold = true;
    await pc.route('**/api/state', async route => {
      if (!hold) return route.continue();
      hold = false;
      const response = await route.fetch();
      captured();
      await responseGate;
      await route.fulfill({response});
    });
    const refreshing = pc.evaluate(() => sync.refresh());
    await responseCaptured;
    await editLevel(pc, 'Cambio con PC sin conexión', 'Guardado más reciente');
    release();
    await refreshing;
    await pc.getByText('Guardado más reciente', {exact: true}).waitFor();
    await mobile.getByText('Guardado más reciente', {exact: true}).waitFor();
    console.log('PASS: una consulta retrasada no deshace el último guardado');

    assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    console.log('PASS: móvil sin desbordamiento y sin errores JavaScript');
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await new Promise(resolve => {if (server.exitCode !== null) resolve(); else server.once('exit', resolve)});
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => {console.error(error);process.exitCode = 1});
