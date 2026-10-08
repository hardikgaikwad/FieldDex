// Pixel sprites as text grids: one character per pixel, "." is transparent.
// The avatar is a 16x16 sprite stacked from layers: back gear, body, hair, chest gear, head gear, hand gear.
const Sprites = (() => {
  const BODY = [
    "................",
    "................",
    ".....KKKKKK.....",
    "....KSSSSSSK....",
    "...KSSSSSSSSK...",
    "...KSSSSSSSSK...",
    "...KSSESSESSK...",
    "...KSMSSSSMSK...",
    "....KSSSSSSK....",
    ".....KKKKKK.....",
    "....KOOOOOOK....",
    "...KOOOOOOOOK...",
    "...KSKOOOOKSK...",
    "....KPPPPPPK....",
    "....KPPKKPPK....",
    "....KBBKKBBK....",
  ];

  const HAIR = {
    short: { 2: ".....HHHHHH.....", 3: "....HHHHHHHH....", 4: "...HHHHHHHHHH...", 5: "...HH......HH..." },
    long: { 2: ".....HHHHHH.....", 3: "....HHHHHHHH....", 4: "...HHHHHHHHHH...", 5: "...HH......HH...",
            6: "...H........H...", 7: "...H........H...", 8: "...HH......HH...", 9: "...HH......HH..." },
    spiky: { 1: "....H.H..H.H....", 2: "....HHHHHHHH....", 3: "...HHHHHHHHHH...", 4: "...HHHHHHHHHH...", 5: "...H........H..." },
    bun: { 0: ".......HH.......", 1: "......HHHH......", 2: ".....HHHHHH.....", 3: "....HHHHHHHH....", 4: "...HHHHHHHHHH...", 5: "...HH......HH..." },
    none: {},
  };

  // Gear unlocked by playing. Each piece lives in one slot.
  const GEAR = {
    explorer_hat: { slot: "head", rows: { 1: ".....TTTTTT.....", 2: ".....tttttt.....", 3: "..TTTTTTTTTTTT.." } },
    leaf_crown: { slot: "head", rows: { 2: "....G.gG.Gg.G...", 3: "....GGGGGGGG...." } },
    camera: { slot: "chest", rows: { 10: "......C..C......", 11: ".....CCCCCC.....", 12: "......CLLC......" } },
    binoculars: { slot: "chest", rows: { 10: ".....C....C.....", 11: ".....CC..CC.....", 12: ".....LC..CL....." } },
    cape: { slot: "back", rows: { 10: "...R........R...", 11: "..RR........RR..", 12: "..RR........RR..",
                                  13: "..RRR......RRR..", 14: "..RRR......RRR..", 15: "...RR......RR..." } },
    bug_net: { slot: "hand", rows: { 5: ".............WW.", 6: "............WWWW", 7: ".............WW.",
                                     8: "..............N.", 9: "..............N.", 10: ".............N..", 11: ".............N..",
                                     12: "............N..." } },
  };
  const SLOT_ORDER = ["back", "body", "hair", "chest", "head", "hand"];

  const OPTIONS = {
    skin: ["#ffdcbd", "#f1c27d", "#d9a066", "#a86b3c", "#7a4a2a"],
    hair: Object.keys(HAIR),
    hairColor: ["#2a1b12", "#5a3a22", "#c48a3a", "#e6c35c", "#d1495b", "#6a5acd", "#e8e8e8"],
    outfit: ["#4cc26a", "#5fcde4", "#ff9f43", "#a26bff", "#ff6b8b", "#f4efe1"],
  };
  const DEFAULT = { skin: 1, hair: "short", hairColor: 0, outfit: 0, gear: {} };

  const FIXED = { K: "#1a1626", E: "#1a1626", M: "#f28b9b", P: "#3b3f6b", B: "#5a3a2a", T: "#c9a26b", t: "#6b4a2b",
                  G: "#4cc26a", g: "#2e7d4f", C: "#2b2b3a", L: "#7fd6ff", W: "#f4efe1", N: "#8a5a3b", R: "#e04b5a" };

  function paint(ctx, rows, colours, scale, dx = 0, dy = 0) {
    for (const [y, row] of Object.entries(rows)) {
      for (let x = 0; x < row.length; x++) {
        const c = colours[row[x]];
        if (!c) continue;
        ctx.fillStyle = c;
        ctx.fillRect((x + dx) * scale, (+y + dy) * scale, scale, scale);
      }
    }
  }

  function drawAvatar(canvas, avatar, scale = 4) {
    const a = { ...DEFAULT, ...(avatar || {}), gear: { ...(avatar?.gear || {}) } };
    canvas.width = 16 * scale;
    canvas.height = 16 * scale;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const colours = { ...FIXED, S: OPTIONS.skin[a.skin] ?? OPTIONS.skin[1], H: OPTIONS.hairColor[a.hairColor] ?? "#2a1b12",
                      O: OPTIONS.outfit[a.outfit] ?? OPTIONS.outfit[0] };
    for (const slot of SLOT_ORDER) {
      if (slot === "body") paint(ctx, Object.fromEntries(BODY.map((r, i) => [i, r])), colours, scale);
      else if (slot === "hair") paint(ctx, HAIR[a.hair] || {}, colours, scale);
      else if (a.gear[slot] && GEAR[a.gear[slot]]) paint(ctx, GEAR[a.gear[slot]].rows, colours, scale);
    }
    return canvas;
  }

  // Monochrome icons; "X" takes the colour passed in.
  const ICONS = {
    today: ["....X....", ".X.....X.", "...XXX...", "..XXXXX..", "X.XXXXX.X", "..XXXXX..", "...XXX...", ".X.....X.", "....X...."],
    reveal: ["XXXXXXX..", "X.....X..", "X..X..XX.", "X.XXX.X.X", "X..X..X.X", "X.....X.X", "XXXXXXX.X", ".X......X", ".XXXXXXXX"],
    dex: ["XXXX.XXXX", "X..X.X..X", "X..X.X..X", "XXXX.XXXX", ".........", "XXXX.XXXX", "X..X.X..X", "X..X.X..X", "XXXX.XXXX"],
    story: [".XXX.XXX.", "X...X...X", "X.X.X.X.X", "X...X...X", "X.X.X.X.X", "X...X...X", "X.X.X.X.X", "X...X...X", ".XXXXXXX."],
    me: ["...XXX...", "..XXXXX..", "..XXXXX..", "...XXX...", ".........", ".XXXXXXX.", "XXXXXXXXX", "XXXXXXXXX", "XXXXXXXXX"],
    bird: [".......", "...XX..", "..XXXXX", "XXXXXX.", ".XXXXX.", "...X.X.", "......."],
    plant: [".....XX", "...XXXX", "..XXXXX", ".XXXXX.", ".XXXX..", "X.XX...", "X......"],
    tree: ["..XXX..", ".XXXXX.", "XXXXXXX", ".XXXXX.", "...X...", "...X...", "..XXX.."],
    insect: ["XX...XX", "XXX.XXX", "XXXXXXX", "..XXX..", "XXXXXXX", "XX.X.XX", "...X..."],
    fungus: ["..XXX..", ".XXXXX.", "XXXXXXX", "...X...", "...X...", "..XXX..", "......."],
    animal: [".X.X.X.", ".X.X.X.", ".......", "..XXX..", ".XXXXX.", ".XXXXX.", "..X.X.."],
    all: ["XX.XX.X", "XX.XX..", ".......", "XX.XX.X", "XX.XX..", ".......", "XX.XX.X"],
  };

  function icon(name, colour, scale = 3) {
    const rows = ICONS[name];
    const c = document.createElement("canvas");
    c.width = rows[0].length * scale;
    c.height = rows.length * scale;
    paint(c.getContext("2d"), Object.fromEntries(rows.map((r, i) => [i, r])), { X: colour }, scale);
    return c;
  }

  return { drawAvatar, icon, OPTIONS, DEFAULT, GEAR };
})();
