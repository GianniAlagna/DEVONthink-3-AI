// Menu probe: records the UUIDs of the selected records and returns at once.
// Installed compiled (.scpt) into ~/Library/Application Scripts/com.devon-technologies.think3/Menu/
ObjC.import('Foundation');

function run() {
    const app = Application('com.devon-technologies.think3');
    let records, via;
    try { records = app.selectedRecords(); via = 'selectedRecords'; }
    catch (e) { records = app.selection(); via = 'selection'; }
    const uuids = records.map(function (r) { return r.uuid(); });
    const dir = $.NSHomeDirectory().js + '/dt3agent-spike/smartrule';
    $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError($(dir), true, $(), $());
    const file = dir + '/' + Date.now() + '-menu.json';
    $(JSON.stringify({ ts: new Date().toISOString(), entry: 'menu', via: via, uuids: uuids }))
        .writeToFileAtomicallyEncodingError($(file), true, $.NSUTF8StringEncoding, $());
}
