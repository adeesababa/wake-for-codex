# Can Wake sell for $0.99?

Assessment date: September 14, 2026. USD; one-time purchase assumed. This is an initial product assessment, not validated customer demand.

## Recommendation

**Technically feasible in a limited workflow; weak as a standalone $0.99 business.** Release and validate the prototype before charging. A $0.99 convenience download can be an acquisition experiment or optional supporter purchase, but it cannot comfortably fund support and ongoing Codex compatibility work.

## Existing alternatives

Public projects already advertise closely overlapping functionality:

- [agent-autoresume](https://github.com/StylesDevelopments/agent-autoresume) offers terminal watchers and a headless wrapper for usage-limit resets, targeting macOS/Linux.
- [codex-dashboard](https://github.com/Justin1491/codex-dashboard) includes usage monitoring and auto-resume for rate-limited non-interactive Codex sessions.

These repository descriptions establish competing functionality, not reliability, sales, or market size. I did not benchmark their code. Demand exists at least at the level of developers building solutions; willingness to pay remains unproven. A Python script alone has little differentiation. A signed Windows installer, reliable desktop integration, clear queue controls, and notifications could justify a convenience premium, but this version does not yet deliver those features.

## Unit economics

Using advertised rates, before tax, refunds, disputes, support, advertising, code signing, and any additional product or payment-method fees:

| Route | Stated fee | Approx. proceeds from $0.99 | Proceeds from 1,000 sales |
|---|---|---:|---:|
| Stripe, standard US domestic card | 2.9% + $0.30 | $0.66 | $661 |
| Gumroad direct card sale | 10% + $0.50, plus 2.9% + $0.30 card processing | $0.06 | $62 |

Calculations: `0.99 - (0.99 × 0.029 + 0.30) = 0.66129`; `0.99 - (0.99 × 0.129 + 0.80) = 0.06229`. Actual per-transaction rounding and applicable charges vary. Gumroad's public pricing headline omits additional card processing; its detailed help page includes it. Its Discover marketplace instead charges 30% including processing, but sales there depend on marketplace discovery and cannot be assumed.

Sources: [Stripe US pricing](https://stripe.com/us/pricing), [Gumroad detailed fees](https://gumroad.com/help/article/66-gumroads-fees), [Gumroad pricing](https://gumroad.com/pricing). Gumroad describes merchant-of-record tax handling; this is not a claim that sellers have no remaining income-tax or reporting obligations.

Illustrative support burden: at an assumed $30/hour, one ten-minute support interaction costs $5 of time—roughly eight Stripe sales or eighty-one Gumroad direct card sales at these estimated margins. At the same assumed rate, twenty hours of development costs $600 of time, requiring approximately 908 Stripe sales before other costs. These are scenarios, not forecasts.

At $4.99, the same Stripe headline formula leaves about $4.55. At $9.99, about $9.40. That gives more room to maintain a convenience utility, provided buyers value the experience. A higher price is a hypothesis to test, not a proven market price.

## Technical and product risks

- Codex's [app-server interface](https://learn.chatgpt.com/docs/app-server) provides the necessary usage and continuation operations, but compatibility changes can create recurring maintenance work.
- The current Windows CLI build does not support the Unix daemon lifecycle. This prototype runs a separate app-server. It cannot guarantee desktop-wide coordination, so exclusive task ownership is required.
- Some desktop tasks rely on tools unavailable to a standalone server. Paginated histories are currently rejected. Approval requests pause automation.
- A computer that sleeps, loses its network, or closes Wake cannot resume work at the reset moment.
- Native Codex improvements or existing free alternatives may eliminate much of the paid value.
- A public repository without a paid convenience layer makes charging for access difficult. Licensing and distribution terms remain undecided; do not promise proprietary exclusivity or an open-source license without choosing one.

## GitHub page versus storefront

The supplied GitHub Pages site is product documentation. GitHub states that Pages is not for sites primarily facilitating commercial transactions or commercial SaaS. Keep an eventual checkout/storefront on a suitable commercial host. [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)

## A small validation experiment

1. Give ten willing Codex users the prototype and record installation completion, unattended reset outcomes, duplicate attempts, and cases needing help. Obtain consent before collecting diagnostics; do not collect task contents or credentials.
2. Require zero duplicate resumptions and ten successful real reset cycles across the declared supported setups before considering a paid release. This is an initial release gate, not proof of universal reliability.
3. Test a $0.99 convenience offer with a small relevant audience through organic discovery. Avoid paid advertising at this margin. Measure actual purchases, refunds, and support minutes; clicks or survey enthusiasm do not establish demand.
4. If users need setup help, either keep it free with optional support or test a $4.99–$9.99 packaged edition after building a simpler install and stronger desktop integration.

**Decision:** proceed as a useful prototype and demand test. Do not treat $0.99 one-time revenue as a sustainable business model yet. No payment collection, paid listing, or sales claim has been activated.
