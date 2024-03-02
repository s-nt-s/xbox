const isLocal = ["", "localhost"].includes(document.location.hostname);
const $$ = (slc) => Array.from(document.querySelectorAll(slc));
const DEMO_AND_TRIAL = Array.from((new Set(DEMO.concat(TRIAL))));
const DEMO_AND_PREVIEW = Array.from((new Set(DEMO.concat(PREVIEW))));
const REAL_GAMES = Array.from(Object.keys(GAME).filter(g => !DEMO_AND_PREVIEW.includes(g)));

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
    "bbb": "price=1-10&reviews=10-38431&rate=4-5",
    "doblado": "lang=vdse+vds+vd",
    "subtitulado": "lang=vdse+vose+se",
    "traducido": "lang=vdse+vds+vd+vose+se+mute"
  })
  static getListType() {
    const m = document.location.search.match(/^\?(gamepass|demos)(&|$)/);
    if (m == null) return null;
    return m[1];
  }
  static form(new_type) {
    const lst = new_type ?? FormQuery.getListType();
    if (["gamepass", "demos"].includes(lst)) {
      document.body.classList.add("noprice");
      $$("#price input").forEach(i => i.disabled = true)
    } else {
      document.body.classList.remove("noprice");
      $$("#price input").forEach(i => i.disabled = false)
    }
    const d = {
      tags: [],
      lang: [],
      range: {},
      gamelist: [],
    };
    if (lst != null && lst.length > 0) d[lst] = true;
    const minmax = /_(max|min)$/;
    document.querySelectorAll("input[id], select[id]").forEach((n) => {
      if (n.disabled) return;
      if (minmax.test(n.id)) return;
      const v = getVal(n.id);
      if (v === false) return;
      if (n.id == "discount" && v === 0) return;
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
    d.gamelist = (() => {
      if (d.gamepass) return GAMEPASS;
      if (d.demos) return DEMO_AND_TRIAL;
      return REAL_GAMES;
    })();
    return d;
  }
  static __form_to_query(new_type) {
    const form = FormQuery.form(new_type);
    const qr = [];
    Object.entries(form).forEach(([k, v]) => {
      if (["mode", "range", "tags", "gamelist", "lang"].includes(k)) return;
      if (k == "order" && v == "D") return;
      if (typeof v == "string") v = encodeURIComponent(v);
      if (v === true) {
        qr.push(k);
        return;
      }
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
    if (form.lang.length)
      qr.push(
        "lang=" + form.lang.map((t) => encodeURIComponent(t)).join("+")
      );
    const query = qr.join("&")
    return FormQuery.REV_QUERY[query] ?? query;
  }
  static form_to_query(new_type) {
    let query = "?" + FormQuery.__form_to_query(new_type);
    if (query == "?") query = "";
    if (document.location.search == query) return;
    const url = document.location.href.replace(/\?.*$/, "");
    history.pushState({}, "", url + query);
  }
  static query_to_form() {
    const query = FormQuery.query();
    if (query == null) return;
    if (query.mode == null) query.mode = firsOptionValue("mode");
    Object.entries(query).forEach(([k, v]) => {
      if (["range", "tags", "lang"].includes(k)) return;
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
    if (query.lang)
      document
        .querySelectorAll('.lang input[type="checkbox"]')
        .forEach((i) => {
          setVal(i.id, query.lang.includes(i.getAttribute("value")));
        });
  }
  static query() {
    const mode = Array.from(document.getElementById("mode").options).map(
      (o) => o.value
    );
    const search = (() => {
      const q = document.location.search.replace(/^\?/, "")
      if (q.length == 0) return null;
      return FormQuery.ALIAS[q] ?? q;
    })();
    const d = {
      tags: [],
      lang: [],
      range: {},
    };
    if (search == null) return d;
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
      if (Array.isArray(d[k])) d[k] = v.split("+").map((t) => decodeURIComponent(t));
      else d[k] = v;
    });
    return d;
  }
  static __get_kv(v) {
    const tmp = v.split("=").flatMap((i) => {
      i = i.trim();
      return i.length == 0 ? [] : i;
    });
    if (tmp.length == 0) return [null, null];
    if (tmp.length > 2 || tmp[0].length == 0) return [null, null];
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
      'select option[value="' + k + '"]'
    );
    if (opt.length == 1) {
      return [opt[0].closest("select[id]").id, k];
    }
    return [k, true];
  }
}
FormQuery.REV_QUERY = Object.freeze(Object.fromEntries(Object.entries(FormQuery.ALIAS).map(([k, v]) => [v, k])))


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

function _filter(form, id) {
  const j = GAME[id];
  if (j == null) {
    console.log(i.id, "no encontrado", i);
    return false;
  }
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

  const lang = (()=> {
    const lang = form.lang;
    if (lang == null || lang.length == 0) return true;
    if (j.spa == null) return lang.includes("null");
    let {audio, subtitles, interface} = j.spa;
    if (audio!== null && subtitles === null) subtitles = interface;
    if (lang.includes("mute") && (audio === null  && subtitles === null))  return true;
    if (lang.includes("vdse") && (audio === true  && subtitles === true))  return true;
    if (lang.includes("vds")  && (audio === true  && subtitles === false)) return true;
    if (lang.includes("vd")   && (audio === true  && subtitles === null))  return true;
    if (lang.includes("vose") && (audio === false && subtitles === true))  return true;
    if (lang.includes("vos")  && (audio === false && subtitles === false)) return true;
    if (lang.includes("vo")   && (audio === false && subtitles === null))  return true;
    if (lang.includes("se")   && (audio === null  && subtitles === true))  return true;
    if (lang.includes("s")    && (audio === null  && subtitles === false)) return true;
    return false;
  })();

  if (!lang) return false;

  return true;
}

function filtrar(new_type) {
  if ((typeof new_type != "string")) new_type = null;
  const form = FormQuery.form(new_type);
  let ok = 0;
  document.querySelectorAll("div.game").forEach(g => g.classList.add("off"));
  form.gamelist.forEach((id) => {
    if (!_filter(form, id)) return;
    const n = document.getElementById('g' + id);
    if (n == null) return;
    n.classList.remove("off");
    ok++;
  });
  if (ok == form.gamelist.length) {
    document.title = `${ok} juegos`;
  } else {
    document.title = `${ok}/${form.gamelist.length} juegos`;
  }
  const div = document.getElementById("games");
  div.classList.remove("hideIfJS");
  if (form.order != div.getAttribute("data-order")) {
    console.log("order", div.getAttribute("data-order"), "->", form.order)
    const _g = (x) => Number(x.getAttribute("data-order-" + form.order.toLocaleLowerCase()))
    $$("div.game").sort((a, b) => _g(a) - _g(b)).forEach(i => div.append(i))
    div.setAttribute("data-order", form.order);
  }
  FormQuery.form_to_query(new_type);
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
    document.querySelectorAll("a.alist").forEach(i => {
      i.addEventListener("click", (e) => {
        history.pushState({}, "", e.target.href);
        FormQuery.query_to_form();
        filtrar();
        //filtrar(i.search.substring(1));
        e.preventDefault();
        e.stopPropagation();
        return false;
      });
    })
    document.querySelectorAll("a.aalias").forEach(i => {
      i.addEventListener("click", (e) => {
        history.pushState({}, "", e.target.href);
        FormQuery.query_to_form();
        filtrar()
        e.preventDefault();
        e.stopPropagation();
        return false;
      });
    })
    FormQuery.query_to_form();
    document.querySelectorAll("input, select").forEach((i) => {
      i.addEventListener("change", filtrar);
    });
    filtrar();
  },
  false
);
