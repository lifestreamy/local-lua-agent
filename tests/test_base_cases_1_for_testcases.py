# Paste this dictionary into TEST_CASES in tests/test_base_cases_data.py
NEW_TEST_CASES = {
    "test_orders_filter_done_01": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  if order.status == \"done\" then\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Оставь в wf.vars.orders только заказы со статусом done."]
    },
    "test_orders_after_date_02": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local y, m, d = string.match(order.createdAt or \"\", \"^(%d%d%d%d)%-(%d%d)%-(%d%d)$\")\n  if y and m and d then\n    local key = tonumber(y) * 10000 + tonumber(m) * 100 + tonumber(d)\n    if key > 20260101 then\n      table.insert(result, order)\n    end\n  end\nend\nreturn result",
        "prompts": ["Верни заказы, созданные после даты 2026-01-01 (дата в order.createdAt как YYYY-MM-DD)."]
    },
    "test_orders_sum_amount_03": {
        "expected": "local total = 0\nfor _, order in ipairs(wf.vars.orders) do\n  total = total + (tonumber(order.amount) or 0)\nend\nreturn total",
        "prompts": ["Посчитай общую сумму заказов по полю amount в wf.vars.orders."]
    },
    "test_orders_max_amount_04": {
        "expected": "if #wf.vars.orders == 0 then\n  return nil\nend\n\nlocal maxAmount = tonumber(wf.vars.orders[1].amount) or 0\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  if amount > maxAmount then\n    maxAmount = amount\n  end\nend\nreturn maxAmount",
        "prompts": ["Найди максимальную сумму заказа в wf.vars.orders по полю amount."]
    },
    "test_orders_min_amount_05": {
        "expected": "if #wf.vars.orders == 0 then\n  return nil\nend\n\nlocal minAmount = tonumber(wf.vars.orders[1].amount) or 0\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  if amount < minAmount then\n    minAmount = amount\n  end\nend\nreturn minAmount",
        "prompts": ["Найди минимальную сумму заказа в wf.vars.orders по полю amount."]
    },
    "test_orders_enrich_high_value_06": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  order.isHighValue = amount >= 10000\n  table.insert(result, order)\nend\nreturn result",
        "prompts": ["Добавь каждому заказу поле isHighValue=true, если amount >= 10000, иначе false."]
    },
    "test_orders_done_ids_07": {
        "expected": "local ids = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  if order.status == \"done\" then\n    table.insert(ids, order.orderId)\n  end\nend\nreturn ids",
        "prompts": ["Верни только номера заказов (orderId) у заказов со статусом done."]
    },
    "test_orders_group_count_status_08": {
        "expected": "local counts = {}\nfor _, order in ipairs(wf.vars.orders) do\n  local status = order.status or \"unknown\"\n  counts[status] = (counts[status] or 0) + 1\nend\nreturn counts",
        "prompts": ["Сгруппируй заказы по статусу и верни словарь вида {status: count}."]
    },
    "test_orders_extract_year_09": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local year = string.match(order.createdAt or \"\", \"^(%d%d%d%d)%-%d%d%-%d%d$\")\n  if year then\n    order.createdAtYear = tonumber(year)\n  else\n    order.createdAtYear = nil\n  end\n  table.insert(result, order)\nend\nreturn result",
        "prompts": ["Для каждого заказа распарсь дату createdAt и добавь поле createdAtYear (только год)."]
    },
    "test_orders_done_net_amount_10": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  if order.status == \"done\" then\n    local amount = tonumber(order.amount) or 0\n    local discount = tonumber(order.discount) or 0\n    order.netAmount = amount - discount\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Верни заказы со статусом done и посчитай в каждом поле netAmount = amount - discount."]
    },
    "test_orders_done_amount_gt_11": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  if order.status == \"done\" and amount > 5000 then\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Оставь заказы, у которых status = done и amount больше 5000."]
    },
    "test_orders_2026_march_12": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local y, m = string.match(order.createdAt or \"\", \"^(%d%d%d%d)%-(%d%d)%-%d%d$\")\n  if y == \"2026\" and m == \"03\" then\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Верни только заказы за март 2026 (createdAt в формате YYYY-MM-DD)."]
    },
    "test_orders_sum_discount_13": {
        "expected": "local totalDiscount = 0\nfor _, order in ipairs(wf.vars.orders) do\n  totalDiscount = totalDiscount + (tonumber(order.discount) or 0)\nend\nreturn totalDiscount",
        "prompts": ["Посчитай общую скидку по всем заказам (поле discount)."]
    },
    "test_orders_max_order_obj_14": {
        "expected": "if #wf.vars.orders == 0 then\n  return nil\nend\n\nlocal bestOrder = wf.vars.orders[1]\nlocal bestAmount = tonumber(bestOrder.amount) or 0\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  if amount > bestAmount then\n    bestAmount = amount\n    bestOrder = order\n  end\nend\nreturn bestOrder",
        "prompts": ["Найди заказ с максимальным amount и верни весь объект заказа."]
    },
    "test_orders_min_order_obj_15": {
        "expected": "if #wf.vars.orders == 0 then\n  return nil\nend\n\nlocal worstOrder = wf.vars.orders[1]\nlocal worstAmount = tonumber(worstOrder.amount) or 0\nfor _, order in ipairs(wf.vars.orders) do\n  local amount = tonumber(order.amount) or 0\n  if amount < worstAmount then\n    worstAmount = amount\n    worstOrder = order\n  end\nend\nreturn worstOrder",
        "prompts": ["Найди заказ с минимальным amount и верни весь объект заказа."]
    },
    "test_orders_add_month_16": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local month = string.match(order.createdAt or \"\", \"^%d%d%d%d%-(%d%d)%-%d%d$\")\n  order.month = month\n  table.insert(result, order)\nend\nreturn result",
        "prompts": ["Добавь каждому заказу поле month из createdAt (YYYY-MM-DD -> MM)."]
    },
    "test_orders_unique_customer_ids_17": {
        "expected": "local result = _utils.array.new()\nlocal seen = {}\nfor _, order in ipairs(wf.vars.orders) do\n  local customerId = order.customerId\n  if customerId ~= nil and not seen[customerId] then\n    seen[customerId] = true\n    table.insert(result, customerId)\n  end\nend\nreturn result",
        "prompts": ["Верни массив клиентов customerId без дублей из wf.vars.orders."]
    },
    "test_orders_overdue_18": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local y, m, d = string.match(order.dueDate or \"\", \"^(%d%d%d%d)%-(%d%d)%-(%d%d)$\")\n  if y and m and d then\n    local key = tonumber(y) * 10000 + tonumber(m) * 100 + tonumber(d)\n    if key < 20260401 then\n      table.insert(result, order)\n    end\n  end\nend\nreturn result",
        "prompts": ["Верни только просроченные заказы (dueDate раньше 2026-04-01)."]
    },
    "test_orders_avg_amount_19": {
        "expected": "if #wf.vars.orders == 0 then\n  return 0\nend\n\nlocal total = 0\nfor _, order in ipairs(wf.vars.orders) do\n  total = total + (tonumber(order.amount) or 0)\nend\nreturn total / #wf.vars.orders",
        "prompts": ["Посчитай средний amount по всем заказам."]
    },
    "test_orders_first_five_20": {
        "expected": "local result = _utils.array.new()\nlocal limit = math.min(5, #wf.vars.orders)\nfor i = 1, limit do\n  table.insert(result, wf.vars.orders[i])\nend\nreturn result",
        "prompts": ["Верни только первые 5 заказов из wf.vars.orders."]
    },
    "test_orders_sort_amount_desc_21": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  table.insert(result, order)\nend\n\ntable.sort(result, function(a, b)\n  return (tonumber(a.amount) or 0) > (tonumber(b.amount) or 0)\nend)\n\nreturn result",
        "prompts": ["Отсортируй заказы по amount по убыванию и верни новый массив."]
    },
    "test_orders_customer_name_a_22": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  local name = order.customerName or \"\"\n  if string.sub(name, 1, 1) == \"A\" then\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Верни заказы, где customerName начинается на \"A\"."]
    },
    "test_orders_done_tax_23": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  if order.status == \"done\" then\n    local amount = tonumber(order.amount) or 0\n    order.taxAmount = amount * 0.2\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Для заказов done добавь поле taxAmount = amount * 0.2."]
    },
    "test_orders_sum_by_status_24": {
        "expected": "local sums = {}\nfor _, order in ipairs(wf.vars.orders) do\n  local status = order.status or \"unknown\"\n  local amount = tonumber(order.amount) or 0\n  sums[status] = (sums[status] or 0) + amount\nend\nreturn sums",
        "prompts": ["Верни словарь сумм по статусам: для каждого status сумма amount."]
    },
    "test_orders_remove_without_id_25": {
        "expected": "local result = _utils.array.new()\nfor _, order in ipairs(wf.vars.orders) do\n  if order.orderId ~= nil and order.orderId ~= \"\" then\n    table.insert(result, order)\n  end\nend\nreturn result",
        "prompts": ["Удали из заказов записи без orderId и верни очищенный массив."]
    },
}
