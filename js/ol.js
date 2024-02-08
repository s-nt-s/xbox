function do_remove() {
    window.__ol__ = document.querySelector("ol");
    window.__ol__.style.display = "none"
    const bt = Array.from(document.querySelectorAll("button")).filter(i => {
        return i.textContent.trim() == "Cargar más"
    }).pop();
    if (bt == null) return;
    const find_parentes = (n) => {
        const arr = [n, document.body];
        while (n.parentNode != document.body) {
            n = n.parentNode;
            arr.push(n);
        }
        return arr;
    }
    const parents = [window.__ol__, bt].map(find_parentes).flatMap((arr, i, full) => {
        if (i > 0) return [];
        const others = full.slice(1).flatMap(a => a);
        return arr.filter(i => others.includes(i))
    })
    const remove_nodes = (n) => {
        if (!parents.includes(n)) {
            n.parentNode.removeChild(n);
            return;
        }
        const chl = Array.from(n.childNodes);
        if (chl.filter(i => parents.includes(i)).length == 0) return;
        chl.forEach(remove_nodes);
    }
    remove_nodes(document.body);
    const bt_path = find_parentes(bt).concat(Array.from(bt.querySelectorAll("*")))
    document.querySelectorAll("body *").forEach(n => {
        if (!bt_path.includes(n)) n.style.display = "none";
    })
}
function do_magic() {
    /*
    document.head.appendChild((() => {
        const s = document.createElement("style");
        s.innerHTML = "ol {display:none !important;} img {display:none !important;}"
        return s;
    })());
    */
    window.__ol__ = document.querySelector("ol");
    if (window.__ol__ == null) {
        setTimeout(do_magic, 1000);
        return
    }
    do_remove();
    setTimeout(do_remove, 20000);
    setInterval(() => {
        window.__ol__.innerHTML = ""
    }, 10000);
    return;
    setInterval(() => {
        const bt = Array.from(document.querySelectorAll("button")).filter(i => {
            return i.textContent.trim() == "Cargar más"
        }).pop();
        if (bt == null) return;
        window.__ol__.innerHTML = ""
        bt.click()
    }, 1000);
}

if (document.readyState == "loading") document.addEventListener("DOMContentLoaded", do_magic)
else do_magic();