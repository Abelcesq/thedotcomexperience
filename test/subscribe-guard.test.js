const test = require('node:test');
const assert = require('node:assert');
const { createGuard, captchaPasses, CODE_TTL_MS, MAX_CODE_ATTEMPTS } = require('../subscribe-guard');

function setup() {
  const clock = { t: 1_800_000_000_000 };
  return { clock, guard: createGuard({ secret: 'test-secret', now: () => clock.t }) };
}

test('the right code redeems the token once and returns the details', () => {
  const { guard } = setup();
  const { code, token } = guard.issue({ e: 'ana@example.com', n: 'Ana', c: 'Davis' });
  assert.match(code, /^\d{6}$/);
  const first = guard.redeem(token, code);
  assert.equal(first.ok, true);
  assert.equal(first.details.e, 'ana@example.com');
  assert.equal(first.details.c, 'Davis');
  assert.equal(guard.redeem(token, code).reason, 'used');
});

test('codes typed with spaces or dashes still work', () => {
  const { guard } = setup();
  const { code, token } = guard.issue({ e: 'a@example.com' });
  assert.equal(guard.redeem(token, code.slice(0, 3) + ' - ' + code.slice(3)).ok, true);
});

test('a wrong code fails, and the token locks after too many guesses', () => {
  const { guard } = setup();
  const { code, token } = guard.issue({ e: 'a@example.com' });
  const wrong = code === '000000' ? '111111' : '000000';
  for (let i = 1; i < MAX_CODE_ATTEMPTS; i++) assert.equal(guard.redeem(token, wrong).reason, 'wrong');
  assert.equal(guard.redeem(token, wrong).reason, 'locked');
  assert.equal(guard.redeem(token, code).reason, 'locked', 'even the right code is refused once locked');
});

test('codes expire', () => {
  const { guard, clock } = setup();
  const { code, token } = guard.issue({ e: 'a@example.com' });
  clock.t += CODE_TTL_MS + 1;
  assert.equal(guard.redeem(token, code).reason, 'expired');
});

test('a token cannot be forged or edited', () => {
  const { guard } = setup();
  const { code, token } = guard.issue({ e: 'real@example.com' });
  const [body, codeSig, seal] = token.split('.');
  const edited = Buffer.from(JSON.stringify(Object.assign(guard.read(token), { e: 'attacker@example.com' })))
    .toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  assert.equal(guard.read([edited, codeSig, seal].join('.')), null, 'edited details are not trusted');
  assert.equal(guard.status([edited, codeSig, seal].join('.')), 'invalid');
  assert.equal(guard.redeem([edited, codeSig, seal].join('.'), code).reason, 'invalid');
  assert.equal(guard.redeem([body, 'AAAA', seal].join('.'), code).reason, 'wrong');
  assert.equal(guard.redeem(body + '.' + codeSig, code).reason, 'invalid');
  assert.equal(guard.redeem('garbage', code).reason, 'invalid');
  assert.equal(guard.redeem('', code).reason, 'invalid');
  const other = createGuard({ secret: 'different-secret' });
  assert.equal(other.read(token), null, 'a token signed with another secret is refused');
});

test('status reports whether a genuine token is still open', () => {
  const { guard, clock } = setup();
  const { code, token } = guard.issue({ e: 'a@example.com' });
  assert.equal(guard.status(token), 'open');
  guard.redeem(token, code);
  assert.equal(guard.status(token), 'used');
  const later = guard.issue({ e: 'b@example.com' });
  clock.t += CODE_TTL_MS + 1;
  assert.equal(guard.status(later.token), 'expired');
});

test('the code is not readable from the token', () => {
  const { guard } = setup();
  const { code, token } = guard.issue({ e: 'a@example.com' });
  assert.equal(JSON.stringify(guard.read(token)).includes(code), false);
});

test('rate limiting allows a burst then blocks until the window passes', () => {
  const { guard, clock } = setup();
  for (let i = 0; i < 3; i++) assert.equal(guard.allow('ip:1.2.3.4', 3, 60_000), true);
  assert.equal(guard.allow('ip:1.2.3.4', 3, 60_000), false);
  assert.equal(guard.allow('ip:5.6.7.8', 3, 60_000), true, 'other visitors are unaffected');
  clock.t += 60_001;
  assert.equal(guard.allow('ip:1.2.3.4', 3, 60_000), true);
});

test('captcha: needs a successful, human-looking answer; lets through only if Google is down', async () => {
  const reply = (data) => ({ fetchImpl: async () => ({ json: async () => data }) });
  const check = (data, extra) => captchaPasses('secret', 'tok', '1.1.1.1', Object.assign(reply(data), extra));
  assert.equal(await check({ success: true, score: 0.9, action: 'subscribe' }, { action: 'subscribe' }), true);
  assert.equal(await check({ success: true, score: 0.5 }), true, 'exactly at the default minimum');
  assert.equal(await check({ success: true, score: 0.3 }), false, 'looks like a bot');
  assert.equal(await check({ success: true, score: 0.3 }, { minScore: 0.2 }), true, 'minimum is adjustable');
  assert.equal(await check({ success: false, 'error-codes': ['invalid-input-response'] }), false);
  assert.equal(await check({ success: true, score: 0.9, action: 'login' }, { action: 'subscribe' }), false, 'token made for another form');
  assert.equal(await captchaPasses('secret', '', '1.1.1.1', reply({ success: true, score: 0.9 })), false, 'no answer at all');
  const originalError = console.error; console.error = () => {};
  assert.equal(await captchaPasses('secret', 'tok', '1.1.1.1', { fetchImpl: async () => { throw new Error('down'); } }), true);
  console.error = originalError;
});
