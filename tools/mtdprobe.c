/*
 * Read one page twice, once through the ECC engine and once raw, and show both.
 * The buffers are pre-filled with 0xa5 so "driver wrote 0xff" is distinguishable
 * from "driver never touched the buffer". The raw read bypasses the ECC engine
 * and the erased-page detector, so it shows what the chip actually returns.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <mtd/mtd-user.h>

static void dump(const char *tag, const unsigned char *b, int n)
{
	int i, allff = 1, alla5 = 1;

	printf("  %-10s", tag);
	for (i = 0; i < n; i++)
		printf("%02x ", b[i]);
	for (i = 0; i < n; i++) {
		if (b[i] != 0xff)
			allff = 0;
		if (b[i] != 0xa5)
			alla5 = 0;
	}
	printf("  %s\n", alla5 ? "<- UNTOUCHED" : allff ? "<- all 0xff" : "");
}

static void one(int fd, unsigned long long off, int raw)
{
	unsigned char data[2048], oob[64];
	struct mtd_read_req req;
	int r;

	memset(data, 0xa5, sizeof(data));
	memset(oob, 0xa5, sizeof(oob));
	memset(&req, 0, sizeof(req));
	req.start = off;
	req.len = sizeof(data);
	req.ooblen = sizeof(oob);
	req.usr_data = (uint64_t)(uintptr_t)data;
	req.usr_oob = (uint64_t)(uintptr_t)oob;
	req.mode = raw ? MTD_OPS_RAW : MTD_OPS_PLACE_OOB;

	errno = 0;
	r = ioctl(fd, MEMREAD, &req);
	printf("%s read at 0x%llx: ioctl=%d errno=%d (%s)\n",
	       raw ? "RAW " : "ECC ", off, r, errno, errno ? strerror(errno) : "ok");
	dump("data", data, 24);
	dump("oob", oob, 24);
}

int main(int argc, char **argv)
{
	unsigned long long off;
	int fd;

	if (argc < 3) {
		fprintf(stderr, "usage: %s /dev/mtdN offset\n", argv[0]);
		return 2;
	}
	fd = open(argv[1], O_RDONLY);
	if (fd < 0) {
		perror("open");
		return 1;
	}
	off = strtoull(argv[2], NULL, 0);

	one(fd, off, 0);
	one(fd, off, 1);
	close(fd);
	return 0;
}
