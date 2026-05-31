# Mini App resources section runtime fix

Исправляет проблему после добавления раздела «Ссылки», когда Mini App открывался, но экран оставался пустым, а нижнее меню не реагировало.

## Причина

В `app/miniapp_static/app.js` перед блоком `RESOURCE_GROUPS` остался отдельный токен:

```js
async
const RESOURCE_GROUPS = [...]
```

В JavaScript это интерпретируется как обращение к переменной `async`, которой нет. Из-за `ReferenceError` выполнение скрипта останавливалось до регистрации обработчиков кликов по вкладкам.

## Исправление

Удален лишний `async` перед `RESOURCE_GROUPS`.

SQL и backend не менялись.
