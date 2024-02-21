const isLocal = ["", "localhost"].includes(document.location.hostname);
const $$ = (slc) => Array.from(document.querySelectorAll(slc));
const TRIAL_AND_DEMO = Array.from((new Set(TRIAL.concat(DEMO))));
const REAL_GAMES = Array.from(Object.keys(GAME).filter(g => !DEMO.includes(g)));

function firsOptionValue(id) {
  const elm = document.getElementById(id);
  if (elm == null || elm.options.length == 0) return null;
  const val = (elm.options[0].value ?? "").trim();
  if (val.length == 0) return null;
  const tp = elm.getAttribute("data-type");
  if (tp == "number") {
    const num = Number(val);
    if (isNaN(num)) return null;
    return num;
  }
  return val;
}

class FormQuery {
  static ALIAS = Object.freeze({
    "bbb": "price=1-10&reviews=10-38431&rate=4-5"
  })
  static form() {
    const lst = getVal("list");
    if (["G", "T"].includes(lst)) {
      document.body.classList.add("noprice");
      $$("#price input").forEach(i=>{
        if (i.disabled) return;
        i.setAttribute("old-value", i.value);
        i.disabled=true;
      })
    } else {
      document.body.classList.remove("noprice");
      $$("#price input").forEach(i=>{
        if (!i.disabled) return;
        setVal(i.id, i.getAttribute("old-value"));
        i.disabled=false;
      })
    }
    const d = {
      tags: [],
      range: {},
      gamelist: [],
    };
    const minmax = /_(max|min)$/;
    document.querySelectorAll("input[id], select[id]").forEach((n) => {
      if (n.disabled) return;
      if (minmax.test(n.id)) return;
      const v = getVal(n.id);
      if (v === false) return;
      if (n.id == "discount" && v === 0) return;
      if (n.id == "antiquity" && v === firsOptionValue("antiquity")) return;
      const nm = n.getAttribute("name");
      if (nm != null) {
        if (!Array.isArray(d[nm])) d[nm] = [];
        d[nm].push(v);
        return;
      }
      d[n.id] = v;
    });
    d.range = getRanges(
      ...new Set(
        $$("input[id$=_max],input[id$=_min]").filter(n => !n.disabled).map((n) =>
          n.id.replace(minmax, "")
        )
      )
    );
    if (d.list == "G") d.gamelist = GAMEPASS;
    if (d.list == "T") d.gamelist = TRIAL_AND_DEMO;
    if (d.list == "A") d.gamelist = REAL_GAMES;
    return d;
  }
  static __form_to_query() {
    const form = FormQuery.form();
    const qr = [];
    if (form.list == "G") qr.push('gamepass');
    if (form.list == "T") qr.push('demo');
    Object.entries(form).forEach(([k, v]) => {
      if (["mode", "range", "tags", "gamelist", "list"].includes(k)) return;
      if (k == "order" && v == "D") return;
      if (typeof v == "string") v = encodeURIComponent(v);
      qr.push(k + "=" + v);
    });
    Object.entries(form.range).forEach(([k, v]) => {
      const n = document.getElementById(k + "_max");
      if (
        Number(n.getAttribute("min")) == v.min &&
        Number(n.getAttribute("max")) == v.max
      )
        return;
      qr.push(k + "=" + v.min + "-" + v.max);
    });
    if (form.tags.length)
      qr.push(
        form.mode + "=" + form.tags.map((t) => encodeURIComponent(t)).join("+")
      );
    const query = qr.join("&");
    return FormQuery.REV_QUERY[query]??query;
  }
  static form_to_query() {
    let query = "?" + FormQuery.__form_to_query();
    if (query == "?") query = "";
    if (document.location.search == query) return;
    const url = document.location.href.replace(/\?.*$/, "");
    history.pushState({}, "", url + query);
  }
  static query_to_form() {
    const query = FormQuery.query();
    if (query == null) return;
    if (query.gamepass) setVal("list", "G");
    else if (query.demo) setVal("list", "T");
    else setVal("list", "A");
    Object.entries(query).forEach(([k, v]) => {
      if (["range", "tags"].includes(k)) return;
      if (document.getElementById(k) == null) return;
      setVal(k, v);
    });
    const _set_rank_val = (n) => {
      const [id, k] = n.id.split("_");
      if (query.range == null || query.range[id] == null || query.range[id][k] == null) {
        n.value = n.getAttribute(k);
        return;
      }
      n.value = query.range[id][k];
    }
    $$("input[id$=_min],input[id$=_max]").forEach(_set_rank_val);
    if (query.range)
      Object.entries(query.range).forEach(([k, v]) => {
        setVal(k + "_min", v["min"]);
        setVal(k + "_max", v["max"]);
      });
    if (query.tags)
      document
        .querySelectorAll('.chkhideshow input[type="checkbox"]')
        .forEach((i) => {
          setVal(i.id, query.tags.includes(i.getAttribute("value")));
        });
  }
  static query() {
    const mode = Array.from(document.getElementById("mode").options).map(
      (o) => o.value
    );
    const search = (()=>{
      const q = document.location.search.replace(/^\?/, "")
      if (q.length==0) return null;
      return FormQuery.ALIAS[q]??q;
    })();
    if (search == null) return null;
    const d = {
      tags: [],
      range: {},
    };
    search.split("&").forEach((i) => {
      const [k, v] = FormQuery.__get_kv(i);
      if (k == null) return;
      if (typeof v == "object") {
        d.range[k] = v;
        return;
      }
      if (mode.includes(k)) {
        d["mode"] = k;
        d.tags = v.split("+").map((t) => decodeURIComponent(t));
        return;
      }
      d[k] = v;
    });
    return d;
  }
  static __get_kv(v) {
    const tmp = v.split("=").flatMap((i) => {
      i = i.trim();
      return i.length == 0 ? [] : i;
    });
    if (tmp.length > 2 || tmp[0] == 0) return [null, null];
    const k = tmp[0];
    if (!isNaN(Number(k))) return [null, null];
    if (tmp.length == 2) {
      const v = tmp[1];
      const n = Number(v);
      if (!isNaN(n)) return [k, n];
      if (v.match(/^\d+-\d+$/)) {
        const [_min, _max] = v
          .split("-")
          .map((i) => Number(i))
          .sort((a, b) => a - b);
        return [k, { min: _min, max: _max }];
      }
      return [k, v];
    }
    const opt = document.querySelectorAll(
      'select[id] option[value="' + k + '"]'
    );
    if (opt.length == 1) {
      return [opt[0].closest("select[id]").id, k];
    }
    return [k, true];
  }
}
FormQuery.REV_QUERY = Object.freeze(Object.fromEntries(Object.entries(FormQuery.ALIAS).map(([k,v])=>[v, k])))


function mkTag(s) {
  const div = document.createElement("div");
  div.innerHTML = s;
  return div.children[0];
}

function getVal(id) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #" + id);
    return null;
  }
  if (elm.tagName == "INPUT" && elm.getAttribute("type") == "checkbox") {
    if (elm.checked === false) return false;
    const v = elm.getAttribute("value");
    if (v != null) return v;
    return elm.checked;
  }
  const val = (elm.value ?? "").trim();
  if (val.length == 0) return null;
  const tp = elm.getAttribute("data-type") || elm.getAttribute("type");
  if (tp == "number") {
    const num = Number(val);
    if (isNaN(num)) return null;
    return num;
  }
  return val;
}

function setVal(id, v) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #" + id);
    return null;
  }
  if (elm.tagName == "INPUT" && elm.getAttribute("type") == "checkbox") {
    if (arguments.length == 1) v = elm.defaultChecked;
    elm.checked = v === true;
    return;
  }
  if (arguments.length == 1) {
    v = elm.defaultValue;
  }
  elm.value = v;
}

function filter(slc, fnc) {
  const ok = [];
  const ko = [];
  document.querySelectorAll(slc).forEach((i) => {
    (fnc(i) ? ok : ko).push(i);
  });
  return {
    ok,
    ko,
  };
}

function getRanges() {
  const rgs = {};
  Array.from(arguments).forEach((k) => {
    let mn = getVal(k + "_min");
    let mx = getVal(k + "_max");
    if (mn == null || mx == null) return;
    rgs[k] = { min: mn, max: mx };
  });
  return rgs;
}

function filtrar() {
  const form = FormQuery.form();
  const { ok, ko } = filter("div.game", (i) => {
    const id = i.id.substring(1);
    const j = GAME[i.id.substring(1)];
    if (j == null) {
      console.log(i.id, "no encontrado", i);
      return true;
    }
    if (!form.gamelist.includes(id)) return false;
    if (j.antiquity != null && j.antiquity > (form.antiquity ?? j.antiquity))
      return false;
    if (j.discount != null && j.discount < (form.discount ?? j.discount)) return false;

    const fl = (() => {
      if (form.tags.length == 0) {
        if (form.mode[0] == "S") return false;
        if (form.mode[0] == "H") return true;
      }
      const hs = form.tags.filter((v) => j.tags.includes(v));
      if (form.mode == "SO") return hs.length > 0;
      if (form.mode == "HO") return hs.length == 0;
      if (form.mode == "SA") return hs.length == form.tags.length;
      if (form.mode == "HA") return hs.length != form.tags.length;
      console.log(form.mode, form.tags, j.tags, hs);
    })();
    if (!fl) return false;

    const ok_rgs = Object.entries(form.range).map(([k, value]) => {
      let vl = j[k];
      if (vl == null) {
        console.log(i.id, "no tine", k);
        return true;
      }
      return vl >= value["min"] && vl <= value["max"];
    });
    if (ok_rgs.includes(false)) return false;

    return true;
  });
  ok.forEach((i) => i.classList.remove("off"));
  ko.forEach((i) => i.classList.add("off"));
  if (ok.length == form.gamelist.length) {
    document.title = `${ok.length} juegos`;
  } else {
    document.title = `${ok.length}/${form.gamelist.length} juegos`;
  }
  const div = document.getElementById("games");
  div.classList.remove("hideIfJS");
  if (form.order != div.getAttribute("data-order")) {
    console.log("order", div.getAttribute("data-order"), "->", form.order)
    const _g = (x) => Number(x.getAttribute("data-order-" + form.order.toLocaleLowerCase()))
    $$("div.game").sort((a, b) => _g(a) - _g(b)).forEach(i => div.append(i))
    div.setAttribute("data-order", form.order);
  }
  FormQuery.form_to_query();
}

function fixAntiguedad() {
  const node = document.getElementById("antiquity");
  if (node == null) return;
  const opts = node.options;
  const head = opts.length - 1;
  const done = [];
  const days_to_lab = (ant) => {
    if (ant < 30) return { txt: "día", num: ant };
    if (ant < 365) return { txt: "mes", num: Math.ceil(ant / 30), s: "es" };
    return { txt: "año", num: Math.ceil(ant / 365) };
  };
  Array.from(opts)
    .reverse()
    .forEach((o, i) => {
      const ant = Number(o.value) + ANTIQUITY;
      const lab = days_to_lab(ant);
      if (done.includes(lab.txt + lab.num)) {
        o.remove();
        return;
      } /*
    if (i>0 && i<head && (lab.num>1 && (lab.num%2)==1)) {
      o.remove();
      return;
    }*/
      done.push(lab.txt + lab.num);
      if (lab.txt != "día" || ANTIQUITY > 0) {
        o.textContent =
          lab.num + " " + lab.txt + (lab.num != 1 ? lab.s ?? "s" : "");
      }
    });
}

function ifLocal() {
  if (!isLocal) return;
  document.querySelectorAll("div.game[id]:not([id='']) > p").forEach((p) => {
    p.appendChild(document.createElement("br"));
    ["action", "product", "preload", "review"].forEach((path, i) => {
      if (i > 0) p.appendChild(document.createTextNode(" - "));
      p.appendChild(
        mkTag(`
      <a href="../rec/${path}/${p.parentNode.id.substring(1)}.json">${path}</a>
    `)
      );
    });
  });
}

function fixImg() {
  document.querySelectorAll("img").forEach((i) => {
    i.addEventListener("error", function () {
      const n = Number(this.getAttribute("data-retry"));
      if (n > 3) return;
      setTimeout(() => {
        this.src = this.src;
        this.setAttribute("data-retry", n + 1);
      }, 3000);
    });
  });
}

function setOrder() {
  const def_order = $$("#order option").filter(o => o.getAttribute("selected") != null)[0].value;
  console.log("order=" + def_order)
  const div = document.getElementById("games");
  div.setAttribute("data-order", def_order);
  div.querySelectorAll("div.game").forEach((d, index) => {
    d.setAttribute("data-order-" + def_order.toLocaleLowerCase(), index);
  })
  document.querySelectorAll('#order option:not([value="' + def_order + '"])').forEach(o => {
    ((v) => {
      if (v == 'T') return $$("a.title").sort((a, b) => a.textContent.trim().localeCompare(b.textContent.trim())).map(t => t.closest("div.game"));
      if (v == 'D') return Object.entries(GAME).map(([k, v]) => [k, v.antiquity]).sort((a, b) => a[1] - b[1]).map(i => document.getElementById("g" + i[0]));
      return [];
    })(o.value).forEach((d, index) => {
      d.setAttribute("data-order-" + o.value.toLocaleLowerCase(), index);
    });
  })

}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    setOrder();
    ifLocal();
    fixImg();
    fixAntiguedad();
    FormQuery.query_to_form();
    document.querySelectorAll("input, select").forEach((i) => {
      i.addEventListener("change", filtrar);
    });
    filtrar();
  },
  false
);
