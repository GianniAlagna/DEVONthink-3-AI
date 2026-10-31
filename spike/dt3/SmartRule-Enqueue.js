// Smart Rule probe: only records the UUIDs it receives and returns at once (DT3 must never wait).
// Installed compiled (.scpt) into ~/Library/Application Scripts/com.devon-technologies.think3/Smart Rules/
ObjC.import('Foundation');

function performsmartrule(records) {
    const uuids = records.map(function (r) { return r.uuid(); });
    const dir = $.NSHomeDirectory().js + '/dt3agent-spike/smartrule';
    $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError($(dir), true, $(), $());
    const file = dir + '/' + Date.now() + '-' + Math.random().toString(36).slice(2) + '.json';
    // Run 4 wrote uuids: [] -> also record how many records DT3 passed in
    $(JSON.stringify({ ts: new Date().toISOString(), entry: 'smartrule', count: records.length, uuids: uuids }))
        .writeToFileAtomicallyEncodingError($(file), true, $.NSUTF8StringEncoding, $());
}
