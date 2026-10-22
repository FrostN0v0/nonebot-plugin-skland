window.paginateEndfieldGacha = ({ maxHeight, maxPools }) => {
  const output = document.getElementById("ef-pages");
  const template = document.getElementById("ef-page-template");
  const sources = Array.from(document.getElementById("ef-source").children);
  const pages = [];
  const fragmentsByPool = new Map();
  output.replaceChildren();

  function pageElement(continuation) {
    const element = template.content.firstElementChild.cloneNode(true);
    if (continuation) element.querySelectorAll("[data-overview]").forEach(section => section.remove());
    return element;
  }

  function newPage() {
    const element = pageElement(pages.length > 0);
    output.append(element);
    const page = { element, body: element.querySelector(".ef-sections"), pools: 0 };
    pages.push(page);
    if (!fits(page)) throw new Error("The report header exceeds the page height limit");
    return page;
  }

  function fits(page) {
    return Math.ceil(page.element.getBoundingClientRect().height) <= maxHeight;
  }

  function categorySection(source) {
    const element = source.cloneNode(false);
    const header = source.querySelector(".ef-category-head").cloneNode(true);
    element.append(header);
    const grid = document.createElement("div");
    grid.className = "ef-category-columns";
    const columns = Array.from({ length: Number(source.dataset.columns) }, () => {
      const column = document.createElement("div");
      column.className = "ef-column";
      grid.append(column);
      return column;
    });
    element.append(grid);
    return { element, columns, poolKeys: new Set() };
  }

  function fullPageCapacity(source) {
    const element = pageElement(true);
    element.querySelector(".ef-sections").append(categorySection(source).element);
    output.append(element);
    const capacity = maxHeight - Math.ceil(element.getBoundingClientRect().height);
    element.remove();
    return capacity;
  }

  function shortestColumn(section) {
    return section.columns.reduce((shortest, column) =>
      column.getBoundingClientRect().height < shortest.getBoundingClientRect().height ? column : shortest);
  }

  function remember(page, section, source, fragment) {
    const key = source.dataset.poolKey;
    if (!fragmentsByPool.has(key)) fragmentsByPool.set(key, []);
    fragmentsByPool.get(key).push(fragment);
    section.poolKeys.add(key);
    page.pools += 1;
  }

  function poolFragment(source, continuation) {
    const fragment = source.cloneNode(false);
    const header = continuation
      ? source.querySelector(".ef-pool-continuation").content.firstElementChild
      : source.querySelector(".ef-pool-head");
    fragment.append(header.cloneNode(true));
    fragment.append(source.querySelector(".ef-periods").cloneNode(false));
    return fragment;
  }

  let page = newPage();
  for (const source of sources) {
    const capacity = fullPageCapacity(source);
    const pools = Array.from(source.querySelector(".ef-category-pools").children);
    let section = null;

    // Keep a category together when it fits a fresh page instead of stranding
    // its first short pool below the preceding category.
    if (pools.length <= maxPools) {
      const preview = categorySection(source);
      page.body.append(preview.element);
      for (const pool of pools) shortestColumn(preview).append(pool.cloneNode(true));
      const columnHeight = Math.max(...preview.columns.map(column => column.getBoundingClientRect().height));
      const fitsCurrentPage = fits(page);
      preview.element.remove();
      if (columnHeight <= capacity && !fitsCurrentPage) page = newPage();
    }

    function nextPage() {
      if (section && !section.poolKeys.size) section.element.remove();
      if (!page.pools && pages.length > 1) {
        throw new Error("A complete gacha event exceeds the page height limit");
      }
      page = newPage();
      section = null;
    }

    for (const pool of pools) {
      const periods = Array.from(pool.querySelector(".ef-periods").children).map(period => ({
        source: period,
        events: Array.from(period.querySelector(".ef-events").children),
      }));
      const keepWhole = pool.getBoundingClientRect().height <= capacity;
      let periodIndex = 0;
      let eventIndex = 0;
      let started = false;
      let finished = false;

      while (!finished) {
        if (!section) {
          section = categorySection(source);
          page.body.append(section.element);
        }
        if (!section.poolKeys.has(pool.dataset.poolKey) && section.poolKeys.size >= maxPools) {
          nextPage();
          continue;
        }
        const column = shortestColumn(section);
        if (keepWhole) {
          const whole = pool.cloneNode(true);
          whole.querySelector(".ef-pool-continuation").remove();
          column.append(whole);
          if (!fits(page)) {
            whole.remove();
            nextPage();
            continue;
          }
          remember(page, section, pool, whole);
          finished = true;
          continue;
        }

        const fragment = poolFragment(pool, started);
        const body = fragment.querySelector(".ef-periods");
        column.append(fragment);
        let added = 0;
        while (periodIndex < periods.length) {
          const period = periods[periodIndex];
          const block = period.source.cloneNode(false);
          block.append(period.source.querySelector(".ef-period-head").cloneNode(true));
          const events = period.source.querySelector(".ef-events").cloneNode(false);
          block.append(events);
          body.append(block);
          while (eventIndex < period.events.length) {
            const event = period.events[eventIndex].cloneNode(true);
            events.append(event);
            if (!fits(page)) {
              event.remove();
              break;
            }
            eventIndex += 1;
            added += 1;
          }
          if (!events.children.length) block.remove();
          if (eventIndex < period.events.length) break;
          periodIndex += 1;
          eventIndex = 0;
        }
        if (!added) {
          fragment.remove();
          nextPage();
          continue;
        }
        remember(page, section, pool, fragment);
        started = true;
        finished = periodIndex === periods.length;
      }
    }
  }

  if (!sources.length) {
    const empty = document.createElement("p");
    empty.className = "ef-empty";
    empty.textContent = "所选范围暂无卡池记录";
    page.body.append(empty);
  }
  for (const fragments of fragmentsByPool.values()) {
    for (const [index, fragment] of fragments.entries()) {
      fragment.querySelector("[data-pool-part]").textContent = fragments.length > 1 ? `${index + 1}/${fragments.length}` : "";
    }
  }
  for (const [index, current] of pages.entries()) {
    current.element.querySelector("[data-page-number]").textContent = String(index + 1);
    current.element.querySelector("[data-page-total]").textContent = String(pages.length);
    if (!fits(current)) throw new Error("The paginated report exceeds the page height limit");
  }
  return pages.length;
};
