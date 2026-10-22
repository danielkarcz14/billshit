#let cfg = toml("/data/config.toml")
#let data = toml("/" + sys.inputs.at("data"))

#let dod = cfg.dodavatel
#let odb = cfg.odberatel + data.at("odberatel", default: (:))
#let nast = cfg.nastaveni
#let mena = nast.at("mena", default: "Kč")
#let vs = data.at("vs", default: data.cislo)

#let tecky = (paint: luma(90), thickness: 0.7pt, dash: "dotted")
#let modra-bg = rgb("#d6edf4")
#let modra-txt = rgb("#1d4f6e")
#let seda-txt = luma(60)
#let akcent = modra-txt

#let datum(d) = if type(d) == datetime { d.display("[day].[month].[year]") } else { str(d) }

#let tisice(n) = {
  let s = str(n)
  let out = ""
  for (i, ch) in s.clusters().enumerate() {
    if i > 0 and calc.rem(s.len() - i, 3) == 0 { out += "\u{00A0}" }
    out += ch
  }
  out
}

#let penize(h) = {
  let a = calc.abs(h)
  let cele = calc.quo(a, 100)
  let hal = str(calc.rem(a, 100))
  if hal.len() < 2 { hal = "0" + hal }
  (if h < 0 { "-" } else { "" }) + tisice(cele) + "," + hal + "\u{00A0}" + mena
}

#let mnozstvi(q) = str(q).replace(".", ",")


#let vydaje = data.at("vydaje", default: 0)
#let polozky = (
  data.at("polozky", default: ())
    // hodinové položky s 0 hod. se na faktuře nezobrazí
    .filter(p => p.at("mnozstvi", default: none) != 0)
    + if vydaje != 0 {
      ((nazev: nast.at("vydaje_nazev", default: "Ostatní náklady spojené s poskytováním služeb"), cena: vydaje),)
    } else { () }
)
#let radky = polozky.map(p => {
  let q = p.at("mnozstvi", default: none)
  let cena-h = int(calc.round(float(p.cena) * 100))
  let celkem-h = int(calc.round(float(if q == none { 1 } else { q }) * float(p.cena) * 100))
  (nazev: p.nazev, mnozstvi: q, jednotka: p.at("jednotka", default: ""), cena: cena-h, celkem: celkem-h)
})
#let soucet = radky.map(r => r.celkem).sum(default: 0)
#if nast.at("zaokrouhlit", default: true) {
  let vyrovnani = int(calc.round(soucet / 100)) * 100 - soucet
  if vyrovnani != 0 {
    radky.push((nazev: "Haléřové vyrovnání", mnozstvi: none, jednotka: "", cena: vyrovnani, celkem: vyrovnani))
    soucet += vyrovnani
  }
}


#let ikona-tel = box(baseline: 20%, image(bytes(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='11' fill='none' stroke='#222' stroke-width='1.6'/><path d='M8.2 6.5l1.8-.4 1.3 3-1.3 1a8 8 0 0 0 3.9 3.9l1-1.3 3 1.3-.4 1.8c-.2.6-.8 1-1.4.9A10.5 10.5 0 0 1 7.3 7.9c-.1-.6.3-1.2.9-1.4z' fill='none' stroke='#222' stroke-width='1.4' stroke-linejoin='round'/></svg>",
), height: 10pt))
#let ikona-mail = box(baseline: 20%, image(bytes(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='11' fill='none' stroke='#222' stroke-width='1.6'/><rect x='6' y='8' width='12' height='8.5' rx='1' fill='none' stroke='#222' stroke-width='1.4'/><path d='M6.3 8.5l5.7 4.5 5.7-4.5' fill='none' stroke='#222' stroke-width='1.4'/></svg>",
), height: 10pt))

#set document(title: "Faktura " + str(data.cislo), author: dod.jmeno)
#set text(font: "PT Sans", size: 8.5pt, lang: "cs", fill: luma(20))
#set par(leading: 0.45em, spacing: 0.45em)
#set page(
  paper: "a4",
  margin: (left: 15mm, right: 12mm, top: 0mm, bottom: 20mm),
  footer-descent: 4mm,
  footer: context {
    set text(size: 8.5pt)
    stack(
      spacing: 1.2mm,
      grid(
        columns: (72mm, 1fr, auto),
        align: horizon,
        [*Vystavil:* #dod.jmeno],
        [#ikona-tel #dod.telefon],
        [#ikona-mail #dod.email],
      ),
      line(length: 100%, stroke: tecky),
      align(right, text(size: 7pt, fill: seda-txt)[Strana #counter(page).display()/#counter(page).final().first()]),
    )
  },
)

// ---------- hlavička ----------
#let levy-sl = 89mm
#block(stroke: (bottom: tecky), spacing: 0pt, grid(
  columns: (levy-sl, 1fr),
  stroke: (x, y) => if x == 0 { (right: tecky) },
  stack(
    block(height: 54mm, width: 100%, inset: (left: 5mm, top: 8mm), stroke: (bottom: tecky), spacing: 0pt)[
      #text(size: 7.5pt, weight: "bold", fill: akcent, tracking: 0.04em)[DODAVATEL] \
      #text(size: 10pt)[#dod.jmeno \ #dod.adresa.join(linebreak())]
      #v(4mm)
      IČ: #dod.ic
      #if "dic" in dod [ \ DIČ: #dod.dic ]
      #v(8mm)
      #text(size: 6.5pt)[#dod.rejstrik]
    ],
    block(height: 30mm, width: 100%, inset: (left: 5mm, top: 12.5mm), spacing: 0pt)[
      #set text(size: 8.5pt)
      #dod.banka: #dod.ucet \
      Variabilní symbol: #vs
      #if dod.at("zpusob_platby", default: "") != "" [ \ Způsob platby: #dod.zpusob_platby ]
    ],
  ),
  // titulek + odběratel
  stack(
    block(height: 27mm, width: 100%, inset: (left: 12.5mm, top: 8.5mm), stroke: (bottom: tecky), spacing: 0pt,
      text(size: 21pt)[Faktura #text(weight: "bold", fill: akcent)[#data.cislo]]),
    block(height: 43mm, width: 100%, inset: (left: 12.5mm, top: 5mm), stroke: (bottom: tecky), spacing: 0pt)[
      #text(size: 7.5pt, weight: "bold", fill: akcent, tracking: 0.04em)[ODBĚRATEL]
      #v(2.5mm)
      #text(size: 11pt)[#odb.nazev]
      #v(2.5mm)
      #text(size: 10pt)[#odb.adresa.join(linebreak())]
    ],
    block(height: 14mm, width: 100%, inset: (left: 12.5mm, top: 4mm), spacing: 0pt, grid(
      columns: (1fr, auto),
      [IČ: #odb.ic #if "dic" in odb [ \ DIČ: #odb.dic ]],
      [Datum vystavení: #datum(data.vystaveno) \ Datum splatnosti: #datum(data.splatnost)],
    )),
  ),
))

// ---------- položky ----------
#{
  set text(size: 8.5pt)
  let hl = (paint: akcent, thickness: 1.6pt)
  let tenka = (paint: luma(150), thickness: 0.6pt)
  show table.cell.where(y: 0): set text(fill: seda-txt)
  table(
    columns: (1fr, 18mm, 17mm, 26mm, 21mm),
    align: (left + horizon, right + horizon, center + horizon, right + horizon, right + horizon),
    inset: (x, y) => (
      left: if x == 0 { 5mm } else { 1mm },
      right: if x == 4 { 3mm } else { 1mm },
      y: 3.1mm,
    ),
    stroke: (x, y) => (
      bottom: if y == 0 or y == radky.len() { hl } else { tenka },
    ),
    table.header(
      table.cell(inset: (left: 5mm, top: 4.5mm, bottom: 3.8mm))[Název položky a popis],
      table.cell(inset: (right: 1mm, top: 4.5mm, bottom: 3.8mm))[Množství],
      table.cell(inset: (top: 4.5mm, bottom: 3.8mm))[Jednotka],
      table.cell(inset: (right: 1mm, top: 4.5mm, bottom: 3.8mm))[Cena položky],
      table.cell(inset: (right: 3mm, top: 4.5mm, bottom: 3.8mm))[Celkem],
    ),
    ..radky.map(r => (
      r.nazev,
      if r.mnozstvi == none { [] } else { mnozstvi(r.mnozstvi) },
      r.jednotka,
      penize(r.cena),
      penize(r.celkem),
    )).flatten(),
  )
}

// ---------- součet, podpis, platební lišta ----------
#v(0pt, weak: true)
#block(width: 100%, height: 46mm, spacing: 0pt, breakable: false, {
  place(top + left, dx: 5mm, dy: 4mm, text(size: 7pt)[Poznámka: #dod.poznamka])
  place(top + left, dx: levy-sl, line(angle: 90deg, length: 30mm, stroke: tecky))
  place(top + right, dx: -5mm, dy: 5.5mm, text(size: 12pt, weight: "bold")[
    Celkem:#h(12mm)#text(fill: akcent, penize(soucet))
  ])
  place(top + left, dx: levy-sl, dy: 14mm, line(length: 100% - levy-sl, stroke: tecky))
  place(top + left, dx: levy-sl + 4mm, dy: 17mm, text(size: 6pt)[Podpis a razítko:])

  let obsah = (
    ("Číslo účtu", dod.ucet),
    ("Variabilní symbol", str(vs)),
    ("Datum splatnosti", datum(data.splatnost)),
    ("Částka k uhrazení", penize(soucet)),
  )
  place(top + left, dy: 33mm, block(width: 100%, height: 12mm, fill: modra-bg, radius: 1.5mm, spacing: 0pt,
    grid(
      columns: (1fr,) * obsah.len(),
      rows: 12mm,
      align: left + horizon,
      inset: (left: 5mm),
      stroke: (x, y) => if x > 0 { (left: (paint: white, thickness: 1.5pt)) },
      ..obsah.map(((popis, hodnota)) => {
        set par(leading: 0.3em)
        text(size: 7pt, fill: modra-txt, popis)
        linebreak()
        text(size: 10.5pt, weight: "bold", fill: modra-txt, hodnota)
      }),
    )))
})
