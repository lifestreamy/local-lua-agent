# Synthetic Lua Examples for MWS Octapi
**Author:** Denis  
**Project:** LocalScript — True Tech Hack 2026

Этот файл содержит синтетические пары:
**Запрос пользователя → Lua-код**, соответствующие правилам среды MWS Octapi.
Примеры используются для обучения и тестирования LLM.

---

## Example 1
ЗАПРОС: Отфильтровать заказы со статусом "paid".

**КОД:**
```lua
local result = _utils.array.new()

for _, order in ipairs(wf.vars.orders or {}) do
    if order.status == "paid" then
        result[#result + 1] = order
    end
end

return result


## Example 2

ЗАПРОС: Отфильтровать заказы со статусами "paid" и "shipped".

КОД:
```lua
local result = _utils.array.new()

for _, order in ipairs(wf.vars.orders or {}) do
    local status = order.status
    if status == "paid" or status == "shipped" then
        result[#result + 1] = order
    end
end

return result


## Example 3

ЗАПРОС: Посчитать общую сумму всех заказов.

КОД:
```lua
local total = 0

for _, order in ipairs(wf.vars.orders or {}) do
    total = total + (tonumber(order.amount) or 0)
end

return total


###  Example 4

```markdown
## Example 4

ЗАПРОС: Посчитать сумму только оплаченных заказов.

КОД:
```lua
local total = 0

for _, order in ipairs(wf.vars.orders or {}) do
    if order.status == "paid" then
        total = total + (tonumber(order.amount) or 0)
    end
end

return total


### Example 5

```markdown
## Example 5

ЗАПРОС: Найти заказ с максимальной суммой.

КОД:
```lua
local maxOrder = nil
local maxAmount = nil

for _, order in ipairs(wf.vars.orders or {}) do
    local amount = tonumber(order.amount) or 0
    if maxAmount == nil or amount > maxAmount then
        maxAmount = amount
        maxOrder = order
    end
end

return maxOrder


###  Example 6

```markdown
## Example 6

ЗАПРОС: Найти заказ с минимальной суммой.

КОД:
```lua
local minOrder = nil
local minAmount = nil

for _, order in ipairs(wf.vars.orders or {}) do
    local amount = tonumber(order.amount) or 0
    if minAmount == nil or amount < minAmount then
        minAmount = amount
        minOrder = order
    end
end

return minOrder


###  Example 7

```markdown
## Example 7

ЗАПРОС: Добавить к каждому заказу признак `isExpensive`, если сумма больше 10000.

КОД:
```lua
local result = _utils.array.new()

for _, order in ipairs(wf.vars.orders or {}) do
    local amount = tonumber(order.amount) or 0

    result[#result + 1] = {
        id = order.id,
        status = order.status,
        amount = order.amount,
        isExpensive = amount > 10000
    }
end

return result


###  Example 8

```markdown
## Example 8

ЗАПРОС: Получить список идентификаторов всех заказов.

КОД:
```lua
local result = _utils.array.new()

for _, order in ipairs(wf.vars.orders or {}) do
    result[#result + 1] = order.id
end

return result


###  Example 9

```markdown
## Example 9

ЗАПРОС: Из даты заказа формата "YYYY-MM-DD" получить год.

КОД:
```lua
local dateStr = wf.vars.orderDate or ""
local year = string.match(dateStr, "^(%d%d%d%d)%-%d%d%-%d%d$")

return year


###  Example 10

```markdown
## Example 10

ЗАПРОС: Оставить только заказы, созданные в 2026 году.

КОД:
```lua
local result = _utils.array.new()

for _, order in ipairs(wf.vars.orders or {}) do
    local createdAt = order.createdAt or ""
    local year = string.match(createdAt, "^(%d%d%d%d)%-%d%d%-%d%d$")

    if year == "2026" then
        result[#result + 1] = order
    end
end

return result


Example 11

ЗАПРОС: Вернуть первый заказ со статусом “pending”.

КОД:
'''lua
for _, order in ipairs(wf.vars.orders or {}) do
    if order.status == "pending" then
        return order
    end
end

return nil


Example 12

ЗАПРОС: Если список заказов пустой, вернуть nil, иначе вернуть последний заказ.

КОД:
'''lua
local orders = wf.vars.orders or {}

if #orders == 0 then
    return nil
end

return orders[#orders]


Example 13

ЗАПРОС: Оставить только клиентов с непустым email.

КОД:
'''lua
local result = _utils.array.new()

for _, client in ipairs(wf.vars.clients or {}) do
    local email = client.email
    if email ~= nil and email ~= "" then
        result[#result + 1] = client
    end
end

return result


Example 14

ЗАПРОС: Для каждого клиента вернуть имя и количество его заказов.

КОД:
'''lua
local result = _utils.array.new()

for _, client in ipairs(wf.vars.clients or {}) do
    local orders = client.orders or {}

    result[#result + 1] = {
        name = client.name,
        ordersCount = #orders
    }
end

return result


Example 15

ЗАПРОС: Из полного имени клиента взять только фамилию.

КОД:
'''lua
local fullName = wf.vars.fullName or ""
local lastName = string.match(fullName, "^([^%s]+)")

return lastName

