const userRepo = require("repository.userRepository");

function getUser(id) {
    return userRepo.findUserById(id);
}

module.exports = { getUser };
