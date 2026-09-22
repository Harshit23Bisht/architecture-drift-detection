const repo = require('./repository'); // Bypassing service layer

function loginUser() {
    repo.findUser();
}