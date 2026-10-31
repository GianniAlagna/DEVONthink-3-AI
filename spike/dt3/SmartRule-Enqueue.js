// Smart Rule probe: only records the UUIDs it receives and returns at once (DT3 must never wait).
// Installed compiled (.scpt) into ~/Library/Application Scripts/com.devon-technologies.think3/Smart Rules/
// Run 5: applied to documents, no file appeared -> write the file even when reading the records fails.
ObjC.import('Foundation');

function performsmartrule(records) {
    const info = { ts: new Date().toISOString(), entry: 'smartrule-jxa', type: typeof records, isArray: Array.isArray(records) };
    try {
        info.count = records.length;
        info.uuids = [];
        for (let i = 0; i < records.length; i++) info.uuids.push(records[i].uuid());
    } catch (e) {
        info.error = String(e);
    }
    const dir = $.NSHomeDirectory().js + '/dt3agent-spike/smartrule';
    $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError($(dir), true, $(), $());
    const file = dir + '/' + Date.now() + '-jxa.json';
    $(JSON.stringify(info)).writeToFileAtomicallyEncodingError($(file), true, $.NSUTF8StringEncoding, $());
}
