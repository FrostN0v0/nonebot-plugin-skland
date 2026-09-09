window.paginateEndfieldGacha = ({ maxHeight, maxPools }) => {
  const output = document.getElementById("ef-pages");
  const template = document.getElementById("ef-page-template");
  const sources = Array.from(document.getElementById("ef-source").children);
  const pages = [];
  const fragmentsByPool = new Map();
  output.replaceChildren();

  function newPage() {
    const element = template.content.firstElementChild.cloneNode(true);
    if (pages.length) element.querySelectorAll("[data-overview]").forEach(section => section.remove());
    output.append(element);
    const page = { element, columns: Array.from(element.querySelectorAll(".ef-column")), categories: new Map() };
    pages.push(page);
    if (element.getBoundingClientRect().height > maxHeight) {
      throw new Error("The report header exceeds the page height limit");
    }
    return page;
  }

  function fits(page) {
    return Math.ceil(page.element.getBoundingClientRect().height) <= maxHeight;
  }

  function makeFragment(source) {
    const fragment = source.cloneNode(false);
    fragment.append(source.querySelector(".ef-pool-head").cloneNode(true));
    fragment.append(source.querySelector(".ef-events").cloneNode(false));
    return fragment;
  }

  function recordFragment(page, task, fragment) {
    const { poolKey: key, category } = task.source.dataset;
    if (!page.categories.has(category)) page.categories.set(category, new Set());
    page.categories.get(category).add(key);
    if (!fragmentsByPool.has(key)) fragmentsByPool.set(key, []);
    fragmentsByPool.get(key).push(fragment);
  }

  const queues = Array.from({ length: 3 }, () => ({ pools: [], next: 0 }));
  const rightPoolOrder = { beginner: 0, standard: 1, joint: 2 };
  for (const source of sources) {
    const category = source.dataset.category;
    const column = category === "special" ? 0 : category === "weapon" ? 1 : 2;
    queues[column].pools.push({
      source,
      events: Array.from(source.querySelector(".ef-events").children),
      height: source.getBoundingClientRect().height,
      offset: 0,
    });
  }
  // Stable sorting preserves newest-first pools within each right-column category.
  queues[2].pools.sort((left, right) =>
    rightPoolOrder[left.source.dataset.category] - rightPoolOrder[right.source.dataset.category]);
  let page = newPage();
  const overview = page.element.querySelectorAll("[data-overview]");
  overview.forEach(section => { section.style.display = "none"; });
  const continuationCapacity = maxHeight - page.element.getBoundingClientRect().height;
  overview.forEach(section => { section.style.removeProperty("display"); });

  while (true) {
    let progressed = false;
    for (let columnIndex = 0; columnIndex < queues.length; columnIndex += 1) {
      const queue = queues[columnIndex];
      const column = page.columns[columnIndex];
      while (queue.next < queue.pools.length) {
        const task = queue.pools[queue.next];
        const { poolKey: key, category } = task.source.dataset;
        const categoryPools = page.categories.get(category);
        if (categoryPools && !categoryPools.has(key) && categoryPools.size >= maxPools) break;
        const fragment = makeFragment(task.source);
        const body = fragment.querySelector(".ef-events");
        column.append(fragment);
        const start = task.offset;
        if (!task.events.length) {
          const empty = document.createElement("p");
          empty.className = "ef-pool-empty";
          empty.textContent = "尚无六星或免费寻访记录";
          body.append(empty);
        }
        while (task.offset < task.events.length) {
          const event = task.events[task.offset].cloneNode(true);
          body.append(event);
          if (!fits(page)) {
            event.remove();
            break;
          }
          task.offset += 1;
        }
        const keepWhole = task.height <= continuationCapacity;
        if (!fits(page) || (task.events.length && task.offset === start)
          || (keepWhole && task.offset < task.events.length)) {
          fragment.remove();
          task.offset = start;
          break;
        }
        recordFragment(page, task, fragment);
        progressed = true;
        if (task.offset < task.events.length) break;
        queue.next += 1;
      }
    }
    if (queues.every(queue => queue.next === queue.pools.length)) break;
    if (!progressed && pages.length > 1) {
      throw new Error("A complete gacha event exceeds the page height limit");
    }
    page = newPage();
  }

  if (!sources.length) {
    const empty = document.createElement("p");
    empty.className = "ef-empty";
    empty.textContent = "所选范围暂无卡池记录";
    page.element.querySelector(".ef-columns").append(empty);
  }
  for (const fragments of fragmentsByPool.values()) {
    for (let index = 0; index < fragments.length; index += 1) {
      fragments[index].querySelector("[data-pool-part]").textContent =
        fragments.length > 1 ? `${index + 1}/${fragments.length}` : "";
    }
  }
  for (let index = 0; index < pages.length; index += 1) {
    const current = pages[index];
    current.element.querySelector("[data-page-number]").textContent = String(index + 1);
    current.element.querySelector("[data-page-total]").textContent = String(pages.length);
    if (!fits(current)) throw new Error("The paginated report exceeds the page height limit");
  }
  return pages.length;
};
