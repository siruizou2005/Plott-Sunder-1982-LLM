# Paper verification — Plott & Sunder (1982), Market 3

Every parameter in `ps1982/params.py` was read off the paper itself rather than taken from
the design document. This closes §14.1 of `plott-sunder-1982-LLM复现设计.md`, which listed
these items as unverified because the OCR was unusable.

**Source**: Charles R. Plott & Shyam Sunder, "Efficiency of Experimental Security Markets
with Insider Information: An Application of Rational-Expectations Models", *Journal of
Political Economy* 90(4), Aug. 1982, pp. 663–698. JSTOR 1831348.
Local copy: `~/Downloads/10-Plott-EfficiencyExperimentalSecurity-1982.pdf`.

**Why OCR fails on this paper**: Tables 1, 2, 3 and 8 are landscape page *images*. `pdftotext`
returns noise for them (`Z E In C14SS<< onS~`). They were read by rendering the pages at
400 dpi, rotating −90°, and inspecting the result:

```
pdftoppm -r 400 -f 8 -l 8 -png 10-Plott-EfficiencyExperimentalSecurity-1982.pdf out
python3 -c "from PIL import Image; Image.open('out-08.png').rotate(-90, expand=True).save('rot.png')"
```

Page map (PDF page numbers, not journal pages): Table 1 = pp. 7–8, Table 2 = p. 10,
Table 3 = p. 13, Table 8 = p. 28. The body text and appendix DO have a clean text layer.

---

## Table 1 — information design, market 3 (PDF p. 8)

| Period | N informed | Precision | Info on card | Posterior P(X) | Actual state |
|---:|---|---|---|---:|:---:|
| 1 | None | … | None | .4 | **Y** |
| 2 | None | … | None | .4 | **Y** |
| 3 | 6 — two of each type | Perfect | Y | 0 | Y |
| 4 | 6 — two of each type | Perfect | X | 1 | X |
| 5 | 6 — two of each type | Perfect | Y | 0 | Y |
| 6 | 6 — two of each type | Perfect | Y | 0 | Y |
| 7 | 6 — two of each type | Perfect | X | 1 | X |
| 8 | 6 — two of each type | Perfect | Y | 0 | Y |
| 9 | 6 — two of each type | Perfect | X | 1 | X |
| 10 | 6 — two of each type | Perfect | Y | 0 | Y |
| 11 | **All** | … | Y | 0 | Y |
| 12 | **All** | … | X | 1 | X |

Prior probability of X: **.4**. Knowledge about others' dividends: "Different investors may
have different dividends". Common knowledge about informed agents: How Many = **No**,
Who = **No**, What Informed Know = **Yes**.

### Two corrections to the design document §2.3

1. **Period 1's realized state is Y, not X.** The sequence is `Y Y Y X Y Y X Y X Y Y X`.
2. **Periods 11 and 12 are "All"**, not "6 insiders". Everyone receives a lettered card, so
   PI ≡ RE in those periods and they carry no identifying power.

Consequence: RE and PI separate only in the state-Y insider periods, which are periods
**3, 5, 6, 8, 10 — five of them, not the six** the design document assumed. That is the
entire statistical power of one session.

Both corrections were confirmed against the original and are the sequence the code runs.
The design document's erroneous sequence is not implemented — there is no research question
it answers.

---

## Table 2 — dividend parameters, market 3 (PDF p. 10)

| Type | N | Certificates | Francs | Fixed cost | $/franc | d(X) | d(Y) | P(X) | P(Y) | E[d] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| I | 4 | 2 | 10,000 | 10,000 | .003 | 400 | 100 | .4 | .6 | 220 |
| II | 4 | 2 | 10,000 | 10,000 | .003 | 300 | 150 | .4 | .6 | 210 |
| III | 4 | 2 | 10,000 | 10,000 | .003 | 125 | 175 | .4 | .6 | 155 |

All values match the design document. ✅

---

## Table 3 — price and allocation predictions, market 3 (PDF p. 13)

| Model | Price: none | Price: X | Price: Y | Holder: none | Holder: X | Holder: Y |
|---|---:|---:|---:|---|---|---|
| PI | 220 | 400 | **220** † | I | I insiders † | I uninformed † |
| RE | 220 | 400 | **175** † | I | I † | **III** † |

† marks the cells where the two models differ. All values match the design document §2.4. ✅

---

## Trading institution — footnote 3 (PDF p. 6), verbatim

> Any buyer (seller) is free at any time to make an oral bid (offer) to buy (sell) one unit
> of the security at a designated price. Such bids and offers are publicly announced and
> recorded. Only one (the last) bid and offer are outstanding at any time. Sellers (buyers)
> are free to accept any public bid (offer) they wish.

**"the last", not "the best"** — confirming that the price-improvement requirement in the
baseline design is a deliberate deviation, not a reading of the paper. See
`docs/design-deltas.md` and the `market3_no_improvement.yaml` arm.

---

## Instruction Set 2 (Appendix, PDF pp. 32–35) — points used verbatim

- "Each franc is worth $0.003 to you. **Do not reveal this number to anyone.**"
- Bingo cage: "forty balls numbered one through forty. If the ball drawn is numbered one
  through sixteen, X-dividend is paid; if the ball drawn is numbered seventeen through
  forty, Y-dividend is paid." (16/40 = .4 ✅ — and the instructions never say "probability".)
- Clue card: "each investor will receive a clue card which will carry one of the following
  three: (i) X, (ii) Y, (iii) a blank. … A blank card tells you nothing about whether the X
  or the Y dividend will be paid."
- "All transactions are for one certificate at a time."
- "Your holdings of certificates may never go below zero. Your francs on hand may never go
  below zero."
- "At the end of each year all your holdings are automatically sold to the experimenter at
  a price of 0."
- "All francs on hand at the end of a year in excess of 10,000 francs are yours to keep."
- "**Any ties in bids or acceptance will be resolved by random choice.**" — the basis for
  the MATCH `n > 1` branch.
- "Except for the bids and their acceptance, you are not to speak to any other subject."
- "Notice that earnings may be different for different investors." (Present in markets 3, 4,
  5; removed in market 2.)

The record sheet (fig. 8) has **18 transaction rows**, and Table 8 reports through the
"eighteenth market action" — corroborating the design document's estimate of 18–25 market
actions per period, and hence the 2–3 round cap.

---

## Other confirmations from the body text

| Question | Answer | Source |
|---|---|---|
| How many no-information periods in market 3? | **Two** | §II: "the first four in 1, the first four in 2, **the first two in 3**, …" |
| Blank cards in no-information periods? | **Yes, in markets 3 and 4** | Appendix Step 3: "In markets 1, 2, and 5 information cards were not distributed in no-information periods. In markets 3 and 4 blank information cards were distributed" |
| How many insiders? | **Two of four per type = 6** | §II: "only one-half (two out of four) of the agents from each dividend (preference) type received information" |
| Are the insiders the same people throughout? | **Yes, and subjects were not told** | §II: "they did not know that the insiders were the same agents throughout the relevant periods" |
| Were market 3's subjects experienced? | **Yes** | §II: "Subjects in markets 3 and 5 had participated in one or more of the earlier markets" |
| How much of the log was visible? | **The latest four or five, on a blackboard** | Appendix Step 3. Market 5 additionally got a photocopy of each period's full log. |
| Period length | 7 minutes, warnings at 5, 6 and 6½ | Appendix Step 3 |

---

## Efficiency measures (§III)

    E  = value(actual allocation) / value(RE allocation)
    TE = [value(actual) − value(no trade)] / [value(RE) − value(no trade)]

Both "conditioned upon information in the market". TE exists because E is flattering at the
endowment: "we have constructed a measure which is zero if no trading takes place."

Derived benchmarks for market 3, asserted in `tests/test_metrics.py`:

| Condition | RE allocation value | No-trade value |
|---|---:|---:|
| state X | 24 × 400 = **9,600** | 8×400 + 8×300 + 8×125 = **6,600** |
| state Y | 24 × 175 = **4,200** | 8×100 + 8×150 + 8×175 = **3,400** |
| no information | 24 × 220 = **5,280** | 8×220 + 8×210 + 8×155 = **4,680** |
